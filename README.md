# Figma → Claude Code

FigmaデザインをClaude APIの4つのAIエージェントパイプラインで解析し、本番品質のReact/Next.jsコードを自動生成するアプリケーション。

## 4つのAIエージェント

| エージェント | 役割 | 入力 | 出力 |
|---|---|---|---|
| 🎨 **Designer** | Figmaデザイン分析 | Figma URL | デザイントークン・コンポーネント一覧 |
| 🏗️ **Architect** | コンポーネント設計 | デザイン分析 | ファイル構成・Props定義・設計書 |
| 💻 **Coder** | コード生成 | 設計書 + デザイン分析 | TSX + Tailwind CSSコード |
| 🔍 **Reviewer** | 品質レビュー | 生成コード + デザイン分析 | スコア・指摘事項・改善提案 |

## パイプラインフロー

```
Figma URL → Designer → Architect → Coder → Reviewer → ZIP出力
```

## セットアップ

```bash
# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .env を編集して API キーを設定
```

### 必要な環境変数

| 変数名 | 説明 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API キー |
| `FIGMA_ACCESS_TOKEN` | Figma パーソナルアクセストークン |

## 使い方

```bash
streamlit run app.py
```

1. サイドバーでAPIキーを設定
2. FigmaのURLを入力
3. 「コード生成を開始」をクリック
4. 4つのエージェントが順番に処理を実行
5. 結果をタブで確認、ZIPでダウンロード

## プロジェクト構造

```
figma_to_claude/
├── app.py                  # Streamlit UI
├── requirements.txt
├── .env.example
└── src/
    ├── claude_client.py    # Claude API共通クライアント
    ├── figma_client.py     # Figma REST APIクライアント
    ├── pipeline.py         # パイプラインオーケストレーター
    └── agents/
        ├── designer_agent.py   # デザイナーエージェント
        ├── architect_agent.py  # アーキテクトエージェント
        ├── coder_agent.py      # コーダーエージェント
        └── reviewer_agent.py   # レビュアーエージェント
```

## 技術スタック

- Python 3.11+
- Anthropic Claude API（Sonnet / Haiku）
- Figma REST API
- Streamlit
