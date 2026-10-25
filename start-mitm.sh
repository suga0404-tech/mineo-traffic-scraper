#!/bin/sh
# 自分の PC で mineo / eo ログインを見る。既定ポート 8080、eonet.jp だけ表示。
set -eu
PORT="${PORT:-8080}"
HOST="${LISTEN_HOST:-0.0.0.0}"
exec mitmproxy \
  --listen-host "$HOST" \
  --listen-port "$PORT" \
  --set 'view_filter=~d eonet.jp'
