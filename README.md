# Figma → Claude Code

Figma URLを入力すると、Claude Code（Antigravity / VSCode）の4つのAIエージェントが自動でデザインを解析し、React/Next.jsコードを生成するブリッジアプリ。

## 仕組み

```
Figma URL
    ↓
🎨 Designer Agent  → Figma MCPでデザイン取得・分析 → design-analysis.md
    ↓
🏗️ Architect Agent → コンポーネント設計            → architecture.md
    ↓
💻 Coder Agent     → コード生成                     → output/
    ↓
🔍 Reviewer Agent  → 品質レビュー + 自動修正         → review.md
```

各エージェントは Claude Code CLI (`claude`) を通じて実行され、Figma MCP でデザインデータに直接アクセスします。

## セットアップ

```bash
# Claude Code CLI が必要
npm install -g @anthropic-ai/claude-code

# Streamlit UI を使う場合
pip install -r requirements.txt
```

## 使い方

### 方法1: Streamlit UI（ブラウザ）

```bash
streamlit run app.py
```

- 「自動パイプライン実行」— 4エージェントを順番に自動実行
- 「Claude Codeで開く」— ターミナルで対話モードのClaude Codeを起動

### 方法2: CLIランチャー

```bash
python launcher.py https://www.figma.com/design/XXXXX/...
```

### 方法3: Claude Code から直接

```bash
cd figma_to_claude
claude
# → "designer エージェントで https://... のデザインを分析して" と入力
```

## プロジェクト構造

```
figma_to_claude/
├── app.py                      # Streamlit UI
├── launcher.py                 # CLIランチャー
├── CLAUDE.md                   # Claude Code用プロジェクト説明
├── .claude.json                # Figma MCP設定
├── .claude/agents/
│   ├── designer.md             # 🎨 デザイナーエージェント
│   ├── architect.md            # 🏗️ アーキテクトエージェント
│   ├── coder.md                # 💻 コーダーエージェント
│   └── reviewer.md             # 🔍 レビュアーエージェント
└── output/                     # 生成されたコード（実行後に作成）
```
