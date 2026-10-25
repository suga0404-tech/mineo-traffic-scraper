# eoID refresh token（mitmproxy + mineo アプリ）

`mineo_traffic.py` が使うのは **`client_id=100064798`** 向けの `refresh_token` だけ。取得は **mineo スマホアプリ**の eoID ログインを mitmproxy で見る（[Qiita 逆引き](https://qiita.com/yuzune27/items/169636571885c9d0ab52) と同系）。スクリプトはパスワードを入力しない。

## Web マイページでは足りないことが多い

ブラウザの **my.mineo.jp** は別クライアント（`client_id=142301018`、`redirect_uri=…/mvno_cp/callback`）です。mitm には **`/oidc/v1/authorize` や `/auth/Login/…` まで**出ても、**`POST /oidc/v1/token` が出ない**ことが多い（トークン交換が Web 側で完結するため）。**Safari / Chrome のマイページログインだけでは refresh_token を取れない**前提で進める。

探す行は常に次。

- ホスト: `login.eonet.jp`
- **Method: POST**
- Path: **`/oidc/v1/token`**
- Response JSON に **`refresh_token`**（Request に **`100064798`** があると確実）

## 推奨: MINI で mitm、iPhone でアプリ

secrets の正本は **mini** の `~/local-ai/secrets/` なので、**MINI 上で mitm を 0.0.0.0:8080** に立て、iPhone の Wi‑Fi プロキシを **MINI の LAN IP（例: 192.168.188.112）:8080** にする。M4 で同じ構造（`0.0.0.0:8080` + iPhone プロキシ → M4 の IP）でもよい。

MINI 側の macOS キーチェーンに CA を入れる必要はない（**CA は iPhone だけ**）。

### 1. MINI で mitmproxy（Grok Bot または人）

venv 例: `~/local-ai/venvs/mitmproxy`

```bash
mitmweb --listen-host 0.0.0.0 --listen-port 8080 \
  --web-host 127.0.0.1 --web-port 8081 \
  --set web_password=mineo-local \
  --no-web-open-browser
```

UI は **MINI 上**または Tailscale 経由で `http://127.0.0.1:8081`（パスワードは起動時に `--set web_password=…` で固定するとよい）。ヘッドレスなら `mitmdump` でもよいが、**token 行は人が UI で見る**。

`127.0.0.1:8080` だけの待ち受けでは **同じ Mac のブラウザ専用**で、iPhone からは届かない。

### 2. iPhone

1. 同じ LAN の Wi‑Fi。
2. **設定 → Wi‑Fi → ⓘ → HTTP プロキシ → 手動** — サーバ: MINI（または M4）の IP、ポート **8080**。
3. **Safari → http://mitm.it** — Apple 用 CA をインストールし、**設定 → 一般 → 証明書信頼設定** で mitmproxy を ON。
4. **mineo アプリ**（Web ではない）— ログアウト → eoID で再ログイン。

### 3. トークンを控える

mitmweb で **`POST …/oidc/v1/token`** → Response の `refresh_token` の値だけコピー。

### 4. 保存（mini）

`~/local-ai/secrets/mineo-traffic.json`（git に置かない）

```json
{
  "refresh_token": "ここに貼る"
}
```

`chmod 600`。`access_token` は空でよい。次回 `python3 mineo_traffic.py` が更新する。refresh は **ワンタイム** — 成功後はスクリプトが書き換えたファイルを正とする。

回線番号: `~/local-ai/orchestrator/tasks/mineo-traffic-scraper/state/config.json` の `tel_num`。

### 5. 後片付け

- iPhone: Wi‑Fi プロキシ **オフ**、不要なら CA / プロファイル削除。
- Mac: mitm **停止**。
- 本番 Mac の Wi‑Fi プロキシを ON にしていたら **OFF**（Cursor 音声等のため）。

### 6. 確認

```bash
python3 mineo_traffic.py
```

exit `0` なら OK。`2` なら token 不正・未設定。

## リスク

- mineo アプリが **証明書ピン留め**している場合、mitm では取れない（要別手段）。
- 非公開 API。`client_id` や URL は変わり得る。

## PC だけで試す場合（参考）

同じ Mac で **システム Wi‑Fi プロキシ 127.0.0.1:8080** + Safari で my.mineo.jp に入っても、上記の理由で **`/oidc/v1/token` が出ない**ことが多い。`start-mitm.sh` / mitmproxy TUI は **TTY のある Terminal.app** で。Cursor 内ターミナルだと `invalid width 0` になりやすい。
