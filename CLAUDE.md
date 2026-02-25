# Figma to Claude Code

このプロジェクトは、FigmaデザインURLからReact/Next.jsコードを自動生成するワークフローです。
4つのAIエージェントが順番にデザインを処理します。

## ワークフロー

1. **Designer** (`designer`) — Figma MCPでデザインを取得・分析 → `design-analysis.md`
2. **Architect** (`architect`) — デザイン分析からコンポーネント設計 → `architecture.md`
3. **Coder** (`coder`) — 設計書に基づきコード生成 → `output/`
4. **Reviewer** (`reviewer`) — コードレビュー + 自動修正 → `review.md`

## Figma MCP

Figma MCPが有効になっています。FigmaのURLを渡すとデザインデータを取得できます。

## 出力先

- `design-analysis.md` — デザイン分析結果
- `architecture.md` — コンポーネント設計書
- `output/` — 生成されたコードファイル
- `review.md` — レビュー結果
