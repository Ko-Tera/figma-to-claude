"""Figma → Claude Code ランチャー — Streamlit UI

Figma URLを入力すると、Claude Code CLIの4エージェントを順番に実行し、
デザイン → 設計 → コード生成 → レビューを自動で行う。
"""

import os
import shutil
import subprocess
import streamlit as st

# プロジェクトルート
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- ページ設定 ----------
st.set_page_config(
    page_title="Figma → Claude Code",
    page_icon="🎨",
    layout="wide",
)

# ---------- ヘッダー ----------
st.title("Figma → Claude Code")
st.caption("Figma URLを入力するとClaude Codeが自動でデザインからコードを生成します")

# ---------- サイドバー ----------
with st.sidebar:
    st.header("エージェント パイプライン")
    st.markdown("""
| # | エージェント | 処理内容 |
|---|------------|---------|
| 1 | 🎨 **Designer** | Figma MCPでデザイン分析 |
| 2 | 🏗️ **Architect** | コンポーネント設計 |
| 3 | 💻 **Coder** | コード生成 |
| 4 | 🔍 **Reviewer** | レビュー + 自動修正 |
""")
    st.divider()
    st.markdown("### 出力ファイル")
    st.markdown("""
- `design-analysis.md` — デザイン分析
- `architecture.md` — 設計書
- `output/` — 生成コード
- `review.md` — レビュー結果
""")

    st.divider()
    model = st.selectbox(
        "Claude Model",
        ["sonnet", "opus", "haiku"],
        index=0,
    )

# ---------- エージェント定義 ----------
AGENTS = [
    {
        "name": "designer",
        "label": "🎨 Designer",
        "prompt_template": "以下のFigma URLのデザインを分析して design-analysis.md を作成してください:\n{url}",
        "output_file": "design-analysis.md",
    },
    {
        "name": "architect",
        "label": "🏗️ Architect",
        "prompt_template": "design-analysis.md を読み込んで architecture.md を作成してください。",
        "output_file": "architecture.md",
    },
    {
        "name": "coder",
        "label": "💻 Coder",
        "prompt_template": "architecture.md と design-analysis.md を読み込んで output/ ディレクトリにコードを生成してください。",
        "output_file": None,  # ディレクトリ
    },
    {
        "name": "reviewer",
        "label": "🔍 Reviewer",
        "prompt_template": "output/ のコードを design-analysis.md と照合してレビューし、問題があれば修正してください。review.md を作成してください。",
        "output_file": "review.md",
    },
]


def run_claude_agent(agent_name: str, prompt: str, model_name: str) -> tuple[str, str]:
    """Claude Code CLIでエージェントを実行する。stdout, stderrのタプルを返す。"""
    cmd = [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--agent", agent_name,
        "--model", model_name,
        prompt,
    ]
    result = subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return result.stdout, result.stderr


def read_file_safe(path: str) -> str | None:
    """ファイルが存在すれば中身を返す。"""
    full = os.path.join(PROJECT_DIR, path)
    if os.path.exists(full):
        with open(full, encoding="utf-8") as f:
            return f.read()
    return None


def list_output_files() -> list[tuple[str, str]]:
    """output/ ディレクトリのファイル一覧を返す。(相対パス, 中身)"""
    output_dir = os.path.join(PROJECT_DIR, "output")
    if not os.path.isdir(output_dir):
        return []
    files = []
    for root, _, names in os.walk(output_dir):
        for name in sorted(names):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, PROJECT_DIR)
            try:
                with open(full, encoding="utf-8") as f:
                    content = f.read()
                files.append((rel, content))
            except (UnicodeDecodeError, OSError):
                files.append((rel, "(バイナリファイル)"))
    return files


# ---------- claude CLI チェック ----------
if not shutil.which("claude"):
    st.error("claude CLI が見つかりません。`npm install -g @anthropic-ai/claude-code` でインストールしてください。")
    st.stop()

# ---------- メイン: URL入力 ----------
figma_url = st.text_input(
    "Figma URL を入力",
    placeholder="https://www.figma.com/design/XXXXX/...",
)

# ---------- 実行モード選択 ----------
col_auto, col_interactive = st.columns(2)

with col_auto:
    auto_run = st.button(
        "自動パイプライン実行",
        disabled=not figma_url,
        type="primary",
        use_container_width=True,
        help="4エージェントを順番に自動実行します",
    )

with col_interactive:
    interactive_run = st.button(
        "Claude Codeで開く (対話モード)",
        disabled=not figma_url,
        use_container_width=True,
        help="ターミナルでClaude Codeの対話セッションを起動します",
    )

# ---------- 対話モード: ターミナルで起動 ----------
if interactive_run and figma_url:
    prompt = f"以下のFigma URLのデザインを分析してコードを生成してください。designer → architect → coder → reviewer の順にエージェントを使ってください:\n{figma_url}"
    # macOS: Terminal.app で claude を起動
    apple_script = f'''
    tell application "Terminal"
        activate
        do script "cd '{PROJECT_DIR}' && claude --dangerously-skip-permissions '{prompt}'"
    end tell
    '''
    subprocess.Popen(["osascript", "-e", apple_script])
    st.success("Terminal.app で Claude Code を起動しました。ターミナルを確認してください。")

# ---------- 自動パイプライン実行 ----------
if auto_run and figma_url:
    st.divider()

    # ステージ表示
    stage_cols = st.columns(4)
    stage_status = {}
    for i, agent in enumerate(AGENTS):
        with stage_cols[i]:
            stage_status[agent["name"]] = st.empty()
            stage_status[agent["name"]].info(f"⏳ {agent['label']}")

    progress_bar = st.progress(0.0)
    log_area = st.empty()

    all_outputs = {}
    error_occurred = False

    for i, agent in enumerate(AGENTS):
        name = agent["name"]
        label = agent["label"]

        # ステータス更新: 実行中
        stage_status[name].warning(f"⚙️ {label} 実行中...")
        progress_bar.progress(i / 4)
        log_area.markdown(f"**{label}** を実行中...")

        # プロンプト構築
        prompt = agent["prompt_template"].format(url=figma_url)

        try:
            stdout, stderr = run_claude_agent(name, prompt, model)
            all_outputs[name] = stdout

            # ステータス更新: 完了
            stage_status[name].success(f"✅ {label}")

        except subprocess.TimeoutExpired:
            stage_status[name].error(f"❌ {label} タイムアウト")
            log_area.error(f"{label} がタイムアウトしました（600秒）")
            error_occurred = True
            break
        except Exception as e:
            stage_status[name].error(f"❌ {label} エラー")
            log_area.error(f"{label} でエラー: {e}")
            error_occurred = True
            break

    if not error_occurred:
        progress_bar.progress(1.0)
        log_area.empty()
        st.success("🎉 全工程が完了しました!")

    # ---------- 結果表示 ----------
    st.divider()
    tab_design, tab_arch, tab_code, tab_review = st.tabs([
        "🎨 デザイン分析",
        "🏗️ 設計書",
        "💻 生成コード",
        "🔍 レビュー結果",
    ])

    with tab_design:
        content = read_file_safe("design-analysis.md")
        if content:
            st.markdown(content)
        else:
            st.info("design-analysis.md がまだ生成されていません")

    with tab_arch:
        content = read_file_safe("architecture.md")
        if content:
            st.markdown(content)
        else:
            st.info("architecture.md がまだ生成されていません")

    with tab_code:
        files = list_output_files()
        if files:
            st.markdown(f"**{len(files)} ファイル** が生成されました")
            for path, content in files:
                ext = os.path.splitext(path)[1].lstrip(".")
                lang = {"tsx": "tsx", "ts": "typescript", "jsx": "jsx", "js": "javascript", "css": "css", "json": "json"}.get(ext, "")
                with st.expander(f"📄 {path}"):
                    st.code(content, language=lang)
        else:
            st.info("output/ にまだファイルが生成されていません")

    with tab_review:
        content = read_file_safe("review.md")
        if content:
            st.markdown(content)
        else:
            st.info("review.md がまだ生成されていません")

    # エージェント出力ログ
    with st.expander("エージェント実行ログ"):
        for name, output in all_outputs.items():
            agent_label = next(a["label"] for a in AGENTS if a["name"] == name)
            st.markdown(f"### {agent_label}")
            st.text(output[:3000] if len(output) > 3000 else output)
