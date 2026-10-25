# mineo-traffic-scraper

mineo アプリが利用する非公開 API（`POST https://api.eonet.jp/mineo/v1/get_traffic_history` 等）から、日次・月次のデータ通信量を取得するための **mini 向けクライアント**（予定）。

- **公式 API ではない。** 仕様変更・利用停止があり得る。過度なアクセスはしない。
- **認証情報**（Bearer / refresh token、`custId`）は git に置かない。[`guard-architecture`](https://github.com/suga0404-tech/guard-architecture) または mini の `~/local-ai/secrets/`。
- **3日10GB の残量**は API に無い想定。日別 MB から rolling 3日を計算する。
- **ローカル推計**（`feth0` バイト）は [`Local-AI-Task-Repository` home-briefing](https://github.com/suga0404-tech/Local-AI-Task-Repository/tree/main/orchestrator/home-briefing) の `mineo-quota.json` が別系統。

## 状態

2026-10-25: [`PLAN.md`](./PLAN.md) に沿って `mineo_traffic.py` 実装済み。トークン未設定では動かない。

## 実行

1. `~/local-ai/secrets/mineo-traffic.json` に `refresh_token` を置く（git 外）。初回は [`TOKEN_SETUP.md`](./TOKEN_SETUP.md)（**mineo アプリ + iPhone プロキシ → MINI/M4 の mitm**。Web マイページだけでは不足しやすい）。
2. `~/local-ai/orchestrator/tasks/mineo-traffic-scraper/state/config.json` に `tel_num`（090…）を書く（[`config.example.json`](./config.example.json) 参照）。`cust_id` が分かれば secrets に直接書いてもよい。
3. mini または LAN 上で:

```bash
python3 mineo_traffic.py
```

stdout と `state/latest.json` に rolling 3日・残り MB。ログは `logs/run.log`（`ok` / `auth` / `network` のみ）。

終了コード: `0` 成功、`2` 再ログイン、`3` ネットワーク／429、`1` その他 API。

## 関連

| 置き場 | 内容 |
| :--- | :--- |
| [`digital-legacy-architecture`](https://github.com/suga0404-tech/digital-legacy-architecture) | mineo / 双WAN / 10GB 方針 |
| [`Local-AI-Task-Repository`](https://github.com/suga0404-tech/Local-AI-Task-Repository) | タスク索引・home-briefing |
