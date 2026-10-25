# eoID refresh token（PC + mitmproxy）

自分の mineo ログインを、自分の PC 上の mitmproxy で見て `refresh_token` を取る。iPhone は使わない。スクリプトはパスワードを入力しない。

## 1. mitmproxy を入れる

```bash
python3 -m pip install mitmproxy
```

## 2. プロキシを起動する

このリポジトリで:

```bash
./start-mitm.sh
```

既定は待ち受け `0.0.0.0:8080`、表示フィルタ `~d eonet.jp`。ポートを変えるときは `PORT=8888 ./start-mitm.sh`。

通常モード（ブラウザのプロキシ設定）を使う。透過モードは OS のリダイレクトが要るので、ここでは使わない。

## 3. ブラウザのプロキシと CA

ログインする PC のブラウザで、HTTP / HTTPS プロキシを次にする。

- ホスト: その PC の IP（同じマシンなら `127.0.0.1`）
- ポート: `8080`（変えた場合はそのポート）

プロキシを通した状態で `http://mitm.it` を開き、表示された **mitmproxy CA** をインストールして信頼する。終わったらブラウザのプロキシは外す。

## 4. eoID でログイン

ブラウザで mineo マイページ（`https://my.mineo.jp`、ログインは `login.eonet.jp`）に eoID で入る。

## 5. トークン応答を探す

mitmproxy の一覧で `login.eonet.jp` の **`POST /oidc/v1/token`** を開く。Enter で中身、レスポンス本文の JSON を見る。

## 6. 保存する

JSON の `refresh_token` の値だけを、次のファイルへ書く（git に置かない）。

`~/local-ai/secrets/mineo-traffic.json`

```json
{
  "refresh_token": "ここに貼る"
}
```

`chmod 600` にする。`access_token` は空でよい。次回 `python3 mineo_traffic.py` が更新する。

refresh token は一度使うと入れ替わる。このファイルをスクリプトが上書きする。

回線番号は別ファイル `~/local-ai/orchestrator/tasks/mineo-traffic-scraper/state/config.json` の `tel_num`。
