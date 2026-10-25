#!/usr/bin/env python3
"""mineo 非公開 API から通信履歴を取得し、直近3日の MB と 10GB 残りを出す。"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tokyo")
REPO_DIR = Path(__file__).resolve().parent
DEFAULT_STATE = Path.home() / "local-ai/orchestrator/tasks/mineo-traffic-scraper/state"
DEFAULT_LOG = Path.home() / "local-ai/orchestrator/tasks/mineo-traffic-scraper/logs/run.log"
DEFAULT_SECRETS = Path.home() / "local-ai/secrets/mineo-traffic.json"

EXIT_OTHER = 1
EXIT_AUTH = 2
EXIT_NETWORK = 3


class AuthError(Exception):
    pass


class NetworkError(Exception):
    pass


class ApiError(Exception):
    pass


def expand(path: str | Path) -> Path:
    return Path(path).expanduser()


def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(config_path: Path | None) -> dict:
    base = load_json(REPO_DIR / "config.example.json")
    if config_path and config_path.exists():
        base.update(load_json(config_path))
    else:
        runtime = expand(base.get("state_dir", DEFAULT_STATE)) / "config.json"
        if runtime.exists():
            base.update(load_json(runtime))
    return base


def append_log(log_path: Path, status: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{stamp} {status}\n")


def save_secrets(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)
    path.chmod(0o600)


def http_post_form(
    url: str,
    form: dict[str, str],
    headers: dict[str, str] | None = None,
    *,
    timeout: float,
) -> tuple[int, dict]:
    body = urllib.parse.urlencode(form).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        if e.code == 401:
            raise AuthError("HTTP 401") from e
        if e.code == 429:
            raise NetworkError("rate limited (HTTP 429)") from e
        raise NetworkError(f"HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise NetworkError(str(e.reason)) from e


def with_retry(fn, *, attempts: int = 2, pause_sec: float = 2.0):
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except NetworkError as e:
            last = e
            if i + 1 < attempts:
                time.sleep(pause_sec)
    assert last is not None
    raise last


def refresh_access_token(cfg: dict, secrets: dict) -> dict:
    refresh = (secrets.get("refresh_token") or "").strip()
    if not refresh:
        raise AuthError("refresh_token がありません。mineo アプリから再取得してください。")
    token_url = cfg["token_url"]
    client_id = str(cfg.get("client_id", "100064798"))

    def call():
        status, payload = http_post_form(
            token_url,
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
            },
            timeout=float(cfg.get("http_timeout_sec", 30)),
        )
        if status >= 400:
            raise NetworkError(f"token HTTP {status}")
        if payload.get("error") == "invalid_token":
            raise AuthError(payload.get("error_description") or "invalid_token")
        access = payload.get("access_token") or payload.get("id_token")
        if not access:
            raise AuthError("token 応答に access_token がありません")
        expires_in = int(payload.get("expires_in") or 86400)
        secrets["access_token"] = access
        secrets["access_expires_at"] = (
            datetime.now(TZ) + timedelta(seconds=expires_in)
        ).isoformat()
        new_refresh = payload.get("refresh_token")
        if new_refresh:
            secrets["refresh_token"] = new_refresh
        return secrets

    return with_retry(call)


def access_token_valid(secrets: dict) -> bool:
    token = (secrets.get("access_token") or "").strip()
    if not token:
        return False
    exp_raw = secrets.get("access_expires_at")
    if not exp_raw:
        return False
    try:
        exp = datetime.fromisoformat(exp_raw)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=TZ)
    except ValueError:
        return False
    return datetime.now(TZ) < exp - timedelta(seconds=60)


def mineo_headers(cfg: dict, access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "appId": str(cfg.get("app_id", "MineoTrafficCli")),
        "appVersion": str(cfg.get("app_version", "1.0.0")),
        "aid": str(cfg.get("aid", "cli")),
    }


def mineo_post(cfg: dict, access_token: str, endpoint: str, form: dict[str, str]) -> dict:
    base = str(cfg.get("api_base", "https://api.eonet.jp/mineo/v1/")).rstrip("/") + "/"
    url = urllib.parse.urljoin(base, endpoint.lstrip("/"))

    def call():
        _status, payload = http_post_form(
            url,
            form,
            mineo_headers(cfg, access_token),
            timeout=float(cfg.get("http_timeout_sec", 30)),
        )
        code = payload.get("resultCode")
        if code == "0022":
            raise AuthError((payload.get("messages") or ["認証エラー"])[0])
        if code != "00":
            msg = (payload.get("messages") or [f"resultCode={code}"])[0]
            raise ApiError(msg or f"resultCode={code}")
        return payload

    return with_retry(call)


def normalize_tel(tel: str) -> str:
    return "".join(ch for ch in tel if ch.isdigit())


def resolve_cust_id(cfg: dict, secrets: dict, access_token: str) -> str:
    existing = (secrets.get("cust_id") or cfg.get("cust_id") or "").strip()
    if existing:
        return existing
    payload = mineo_post(cfg, access_token, "get_telnum_list", {})
    lines = payload.get("telNumList") or []
    want = normalize_tel(str(cfg.get("tel_num") or ""))
    if not want:
        raise ApiError("config の tel_num を設定してください（cust_id 自動解決に必要）")
    for row in lines:
        if normalize_tel(str(row.get("telNum") or "")) == want:
            cust = str(row.get("custId") or "").strip()
            if cust:
                secrets["cust_id"] = cust
                return cust
    raise ApiError("tel_num に一致する回線が get_telnum_list にありません")


def daily_mb_map(monthly_list: list, ref: date) -> dict[date, int]:
    out: dict[date, int] = {}
    for month_block in monthly_list or []:
        try:
            month = int(month_block.get("targetMonth"))
        except (TypeError, ValueError):
            continue
        year = ref.year if month <= ref.month else ref.year - 1
        for day_row in month_block.get("dailyTrafficHistoryList") or []:
            try:
                day = int(day_row.get("targetDay"))
            except (TypeError, ValueError):
                continue
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            mb = int(day_row.get("dataTraffic") or 0)
            out[d] = mb
    return out


def rolling_window(ref: date) -> tuple[date, list[date]]:
    yesterday = ref - timedelta(days=1)
    days = [yesterday - timedelta(days=i) for i in range(3)]
    days.sort()
    return yesterday, days


def build_report(cfg: dict, daily: dict[date, int], ref: datetime) -> dict:
    ref_d = ref.date()
    history_through, window = rolling_window(ref_d)
    quota_mb = int(cfg.get("quota_mb", 10240))
    day_rows = [{"date": d.isoformat(), "mb": daily.get(d, 0)} for d in window]
    rolling = sum(row["mb"] for row in day_rows)
    remaining = max(0, quota_mb - rolling)
    return {
        "as_of": ref.isoformat(),
        "history_through": history_through.isoformat(),
        "days": day_rows,
        "rolling_3d_mb": rolling,
        "quota_mb": quota_mb,
        "remaining_mb": remaining,
    }


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    config_path = None
    if argv and argv[0] == "--config":
        config_path = expand(argv[1])
        argv = argv[2:]

    cfg = load_config(config_path)
    secrets_path = expand(cfg.get("secrets_path", DEFAULT_SECRETS))
    state_dir = expand(cfg.get("state_dir", DEFAULT_STATE))
    log_path = expand(cfg.get("log_path", DEFAULT_LOG))
    status = "ok"

    try:
        secrets = load_json(secrets_path)
        if not access_token_valid(secrets):
            secrets = refresh_access_token(cfg, secrets)
            save_secrets(secrets_path, secrets)

        access = secrets["access_token"]
        cust_id = resolve_cust_id(cfg, secrets, access)
        if secrets.get("cust_id"):
            save_secrets(secrets_path, secrets)

        history = mineo_post(cfg, access, "get_traffic_history", {"custId": cust_id})
        ref = datetime.now(TZ)
        daily = daily_mb_map(history.get("monthlyTrafficHistoryList") or [], ref.date())
        report = build_report(cfg, daily, ref)

        state_dir.mkdir(parents=True, exist_ok=True)
        out_path = state_dir / "latest.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except AuthError as e:
        status = "auth"
        print(f"再ログインが必要: {e}", file=sys.stderr)
        return EXIT_AUTH
    except NetworkError as e:
        status = "network"
        print(f"network: {e}", file=sys.stderr)
        return EXIT_NETWORK
    except ApiError as e:
        status = "error"
        print(f"api: {e}", file=sys.stderr)
        return EXIT_OTHER
    except OSError as e:
        status = "network"
        print(f"os: {e}", file=sys.stderr)
        return EXIT_NETWORK
    finally:
        append_log(log_path, status)


if __name__ == "__main__":
    raise SystemExit(main())
