# mineo-traffic-scraper

mineo アプリが利用する非公開 API（`POST https://api.eonet.jp/mineo/v1/get_traffic_history` 等）から、日次・月次のデータ通信量を取得するための **mini 向けクライアント**（予定）。

- **公式 API ではない。** 仕様変更・利用停止があり得る。過度なアクセスはしない。
- **認証情報**（Bearer / refresh token、`custId`）は git に置かない。[`guard-architecture`](https://github.com/suga0404-tech/guard-architecture) または mini の `~/local-ai/secrets/`。
- **3日10GB の残量**は API に無い想定。日別 MB から rolling 3日を計算する。
- **ローカル推計**（`feth0` バイト）は [`Local-AI-Task-Repository` home-briefing](https://github.com/suga0404-tech/Local-AI-Task-Repository/tree/main/orchestrator/home-briefing) の `mineo-quota.json` が別系統。

## 状態

2026-10-25: リポジトリのみ。スクリプト未実装。

## 関連

| 置き場 | 内容 |
| :--- | :--- |
| [`digital-legacy-architecture`](https://github.com/suga0404-tech/digital-legacy-architecture) | mineo / 双WAN / 10GB 方針 |
| [`Local-AI-Task-Repository`](https://github.com/suga0404-tech/Local-AI-Task-Repository) | タスク索引・home-briefing |
