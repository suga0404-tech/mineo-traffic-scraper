# mineo-traffic-scraper 実装計画

仕様の正本は Local-AI-Task-Repository の Task 22（`tasks/mineo-traffic-scraper.md`）。実装先はこのリポジトリ。スクレイパー本体は未実装。このファイルが実装前の計画である。

## 1. 認証

mineo は公式の開発者 API を出していない。アプリが叩く非公開 API（[Qiita 逆引き](https://qiita.com/yuzune27/items/169636571885c9d0ab52)）を使う。

- 初回だけ人が eoID で mineo アプリにログインし、`refresh_token` を mitm 等で取る（スクリプトはパスワードを入力しない）。
- 実行時: access が切れていれば `POST https://login.eonet.jp/oidc/v1/token`。body は `grant_type=refresh_token`、`refresh_token`、`client_id=100064798`。
- 応答の `access_token` を `Authorization: Bearer` に使う。`expires_in` は約 86400 秒。
- **refresh_token は一度きり。** 成功したら新しい refresh を必ず上書き保存する。失敗した古い token は捨てる。
- `custId` が未設定なら `POST https://api.eonet.jp/mineo/v1/get_telnum_list`（custId 不要）で回線一覧を取り、設定の電話番号と一致する行を使う。
- 保存先: `~/local-ai/secrets/mineo-traffic.json`（mode 600）。git に置かない。中身は `refresh_token`、`access_token`、`access_expires_at`、`cust_id`。正本の置き場の説明は guard-architecture。Task 13 の age ストアとは混ぜない。

## 2. get_traffic_history

- `POST https://api.eonet.jp/mineo/v1/get_traffic_history`
- Headers: `Authorization: Bearer <access>`、`appId`、`appVersion`、`aid`（コミュニティ例は任意文字列で通る、とされている。壊れたらアプリの実値に合わせる）
- Body: `application/x-www-form-urlencoded` の `custId`
- 成功 `resultCode` `"00"`。`monthlyTrafficHistoryList[]` に月ごと:
  - `targetMonth`、`sumInfo.dataTraffic`（月合計、判定には使わない）
  - `dailyTrafficHistoryList[]`: `targetDay`、`dataTraffic`（通常）、`dataTrafficHighSpeed`、`dataTrafficLowSpeed`
- 履歴は前日まで。当日は欠ける。

## 3. 3日 10GB

- 当月（必要なら前月）の日別を日付に展開し、**今日を除く直近3暦日**の `dataTraffic` を足す（「通常」列）。
- 上限の既定は Task 22 どおり **10 GiB = 10240 MiB**（`10737418240` バイト）。mineo 画面の「10GB」が 10000 MB なのか 10240 MB なのかは未確認（リスク）。
- `remaining_mb = max(0, quota_mb - rolling_3d_mb)`。
- 当日分は足さない（API に無い）。ログに `history_through` を残す。

## 4. 出力

- stdout: JSON 1個。`as_of`、`history_through`、`days`（直近3日の date と mb）、`rolling_3d_mb`、`quota_mb`、`remaining_mb`。トークンは出さない。
- ファイル: `~/local-ai/orchestrator/tasks/mineo-traffic-scraper/state/latest.json`（同じ JSON）。
- ログ: `.../logs/run.log` に時刻と `ok` / `auth` / `network` だけ。値も秘密も書かない。
- home-briefing の §3 はまだ触らない（Task 22）。

## 5. エラー

- ネットワーク失敗・タイムアウト: exit 3。リトライは1回、間隔を空ける。
- HTTP 401、`resultCode` `0022`、refresh の `invalid_token`: exit 2。メッセージは「再ログインが必要」。パスワード入力はしない。
- `0098` などその他: exit 1。`messages` の先頭だけ（秘密が無い前提）。
- 連続失敗でもループしない。cron は 1日1回まで。

## 6. ファイル構成（実装時）

- `mineo_traffic.py` — refresh、履歴取得、rolling、JSON 出力
- `config.example.json` — `quota_mb`（10240）、`tel_num` 空、`state_dir`、`log_path`。秘密は無し
- 実行時設定は `~/local-ai/.../state/config.json` か環境変数。リポには example のみ
- `.gitignore` は既存のまま（`.env`、`token.json`、`secrets/`）
- `PLAN.md` — 本計画
- README の「状態」行は、この計画を置いた時点で「PLAN あり・未実装」にする

## 7. リスク

- 非公開 API。URL・ヘッダ・`client_id` は予告なく変わる。
- refresh は一度きりなので、保存に失敗すると人が取り直す。
- 10GB の単位（10000 vs 10240 MB）が mineo の実制限とずれる可能性。
- 当日通信は見えない。32kbps 中かどうかは `dataTrafficLowSpeed` があっても「翌日制限」そのものではない。
- 利用規約上、自動化は自己責任。頻度を上げない。
