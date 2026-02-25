"""Figma → Claude Code ランチャー — Streamlit UI

Figma URL または デザイン画像を入力すると、Claude Code CLIの4エージェントを順番に実行し、
デザイン → 設計 → コード生成 → レビューを自動で行う。
"""

import io
import os
import shutil
import subprocess
import zipfile
from datetime import datetime
import streamlit as st

# プロジェクトルート
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(PROJECT_DIR, "uploads")
EXPORTS_DIR = os.path.join(PROJECT_DIR, "exports")

# ---------- ページ設定 ----------
st.set_page_config(
    page_title="Figma → Claude Code",
    page_icon="🎨",
    layout="wide",
)

# ---------- セッションステート初期化 ----------
if "pipeline_done" not in st.session_state:
    st.session_state.pipeline_done = False
if "active_tab" not in st.session_state:
    st.session_state.active_tab = None
if "all_outputs" not in st.session_state:
    st.session_state.all_outputs = {}
if "error_msg" not in st.session_state:
    st.session_state.error_msg = None

# ---------- ヘッダー ----------
st.title("Figma → Claude Code")
st.caption("Figma URL またはデザイン画像からClaude Codeが自動でコードを生成します")

# ---------- サイドバー ----------
with st.sidebar:
    st.header("エージェント パイプライン")
    st.markdown("""
| # | エージェント | 処理内容 |
|---|------------|---------|
| 1 | 🎨 **Designer** | デザイン分析 |
| 2 | 🏗️ **Architect** | コンポーネント設計 |
| 3 | 💻 **Coder** | コード生成 |
| 4 | 🔍 **Reviewer** | レビュー + 自動修正 |
""")
    st.divider()
    st.markdown("### 出力ファイル")
    st.markdown(f"""
- `{PROJECT_DIR}/design-analysis.md`
- `{PROJECT_DIR}/architecture.md`
- `{PROJECT_DIR}/output/`
- `{PROJECT_DIR}/review.md`
""")

    st.divider()
    model = st.selectbox(
        "Claude Model",
        ["sonnet", "opus", "haiku"],
        index=0,
    )

    # 過去のエクスポート一覧
    exports = list_exports()
    if exports:
        st.divider()
        st.markdown(f"### 過去のエクスポート ({len(exports)}件)")
        for fname, fpath in exports:
            with open(fpath, "rb") as f:
                st.download_button(
                    label=f"📦 {fname}",
                    data=f.read(),
                    file_name=fname,
                    mime="application/zip",
                    key=f"export_{fname}",
                    use_container_width=True,
                )

# ---------- エージェント定義 ----------
AGENTS = [
    {
        "name": "designer",
        "label": "🎨 Designer",
        "output_file": "design-analysis.md",
        "tab": "🎨 デザイン分析",
    },
    {
        "name": "architect",
        "label": "🏗️ Architect",
        "prompt": "design-analysis.md を読み込んで architecture.md を作成してください。",
        "output_file": "architecture.md",
        "tab": "🏗️ 設計書",
    },
    {
        "name": "coder",
        "label": "💻 Coder",
        "prompt": "architecture.md と design-analysis.md を読み込んで output/ ディレクトリにコードを生成してください。",
        "output_file": None,
        "tab": "💻 生成コード",
    },
    {
        "name": "reviewer",
        "label": "🔍 Reviewer",
        "prompt": "output/ のコードを design-analysis.md と照合してレビューし、問題があれば修正してください。review.md を作成してください。",
        "output_file": "review.md",
        "tab": "🔍 レビュー結果",
    },
]


def build_designer_prompt(figma_url: str | None, image_paths: list[str] | None) -> str:
    """Designer エージェント用のプロンプトを構築する。"""
    if figma_url:
        return f"以下のFigma URLのデザインを分析して design-analysis.md を作成してください:\n{figma_url}"

    if image_paths:
        paths_str = "\n".join(f"- {p}" for p in image_paths)
        return (
            f"以下のデザイン画像ファイルを Read ツールで読み込んで分析し、design-analysis.md を作成してください。\n"
            f"画像ファイル:\n{paths_str}"
        )

    return ""


def save_uploaded_images(uploaded_files) -> list[str]:
    """アップロードされた画像をuploads/に保存し、フルパスのリストを返す。"""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    paths = []
    for uploaded in uploaded_files:
        dest = os.path.join(UPLOADS_DIR, uploaded.name)
        with open(dest, "wb") as f:
            f.write(uploaded.getbuffer())
        paths.append(dest)
    return paths


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
    """output/ ディレクトリのファイル一覧を返す。(フルパス, 中身)"""
    output_dir = os.path.join(PROJECT_DIR, "output")
    if not os.path.isdir(output_dir):
        return []
    files = []
    for root, _, names in os.walk(output_dir):
        for name in sorted(names):
            full = os.path.join(root, name)
            try:
                with open(full, encoding="utf-8") as f:
                    content = f.read()
                files.append((full, content))
            except (UnicodeDecodeError, OSError):
                files.append((full, "(バイナリファイル)"))
    return files


def save_to_exports(zip_data: bytes) -> str:
    """ZIPデータをexports/にタイムスタンプ付きで保存し、フルパスを返す。"""
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"figma-output_{timestamp}.zip"
    filepath = os.path.join(EXPORTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(zip_data)
    return filepath


def list_exports() -> list[tuple[str, str]]:
    """exports/内のZIPファイル一覧を返す。(ファイル名, フルパス) 新しい順。"""
    if not os.path.isdir(EXPORTS_DIR):
        return []
    files = []
    for name in os.listdir(EXPORTS_DIR):
        if name.endswith(".zip"):
            files.append((name, os.path.join(EXPORTS_DIR, name)))
    files.sort(key=lambda x: x[0], reverse=True)
    return files


def build_zip() -> bytes | None:
    """全出力ファイルを1つのZIPにまとめて返す。"""
    buf = io.BytesIO()
    file_count = 0

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # design-analysis.md
        da = read_file_safe("design-analysis.md")
        if da:
            zf.writestr("design-analysis.md", da)
            file_count += 1

        # architecture.md
        arch = read_file_safe("architecture.md")
        if arch:
            zf.writestr("architecture.md", arch)
            file_count += 1

        # review.md
        rev = read_file_safe("review.md")
        if rev:
            zf.writestr("review.md", rev)
            file_count += 1

        # output/ ディレクトリ内の全ファイル
        output_dir = os.path.join(PROJECT_DIR, "output")
        if os.path.isdir(output_dir):
            for root, _, names in os.walk(output_dir):
                for name in names:
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, PROJECT_DIR)
                    try:
                        with open(full, "rb") as f:
                            zf.writestr(rel, f.read())
                        file_count += 1
                    except OSError:
                        pass

    if file_count == 0:
        return None

    return buf.getvalue()


# ---------- claude CLI チェック ----------
if not shutil.which("claude"):
    st.error("claude CLI が見つかりません。`npm install -g @anthropic-ai/claude-code` でインストールしてください。")
    st.stop()

# ---------- 入力方法の選択 ----------
input_mode = st.radio(
    "入力方法を選択",
    ["Figma URL", "画像アップロード"],
    horizontal=True,
)

figma_url = None
uploaded_images = None
image_paths = None

if input_mode == "Figma URL":
    figma_url = st.text_input(
        "Figma URL を入力",
        placeholder="https://www.figma.com/design/XXXXX/...",
    )
    has_input = bool(figma_url)
else:
    uploaded_images = st.file_uploader(
        "デザイン画像をアップロード（複数可）",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )
    has_input = bool(uploaded_images)

    # プレビュー表示
    if uploaded_images:
        cols = st.columns(min(len(uploaded_images), 4))
        for i, img in enumerate(uploaded_images):
            with cols[i % 4]:
                st.image(img, caption=img.name, use_container_width=True)

# ---------- 実行モード選択 ----------
col_auto, col_interactive = st.columns(2)

with col_auto:
    auto_run = st.button(
        "自動パイプライン実行",
        disabled=not has_input,
        type="primary",
        use_container_width=True,
        help="4エージェントを順番に自動実行します",
    )

with col_interactive:
    interactive_run = st.button(
        "Claude Codeで開く (対話モード)",
        disabled=not has_input,
        use_container_width=True,
        help="ターミナルでClaude Codeの対話セッションを起動します",
    )

# ---------- 画像の保存（実行時） ----------
if (auto_run or interactive_run) and uploaded_images:
    image_paths = save_uploaded_images(uploaded_images)

# ---------- 対話モード: ターミナルで起動 ----------
if interactive_run and has_input:
    prompt = build_designer_prompt(figma_url, image_paths)
    full_prompt = f"以下の入力からデザインを分析してコードを生成してください。designer → architect → coder → reviewer の順にエージェントを使ってください:\n{prompt}"
    apple_script = f'''
    tell application "Terminal"
        activate
        do script "cd '{PROJECT_DIR}' && claude --dangerously-skip-permissions '{full_prompt}'"
    end tell
    '''
    subprocess.Popen(["osascript", "-e", apple_script])
    st.success("Terminal.app で Claude Code を起動しました。ターミナルを確認してください。")

# ---------- 自動パイプライン実行 ----------
if auto_run and has_input:
    st.session_state.pipeline_done = False
    st.session_state.all_outputs = {}
    st.session_state.error_msg = None
    st.session_state.active_tab = None

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

    results_container = st.container()
    error_occurred = False

    for i, agent in enumerate(AGENTS):
        name = agent["name"]
        label = agent["label"]
        output_file = agent["output_file"]

        # ステータス更新: 実行中
        stage_status[name].warning(f"⚙️ {label} 実行中...")
        progress_bar.progress(i / 4)
        log_area.markdown(f"**{label}** を実行中...")

        # プロンプト構築
        if name == "designer":
            prompt = build_designer_prompt(figma_url, image_paths)
        else:
            prompt = agent["prompt"]

        try:
            stdout, stderr = run_claude_agent(name, prompt, model)
            st.session_state.all_outputs[name] = stdout

            # ステータス更新: 完了 + 出力パス表示
            if output_file:
                full_path = os.path.join(PROJECT_DIR, output_file)
                stage_status[name].success(f"✅ {label}\n`{full_path}`")
            else:
                full_path = os.path.join(PROJECT_DIR, "output/")
                stage_status[name].success(f"✅ {label}\n`{full_path}`")

            # 完了したエージェントの結果をすぐに表示
            with results_container:
                st.markdown("---")
                st.subheader(f"{label} — 完了")
                if output_file:
                    content = read_file_safe(output_file)
                    if content:
                        full_path = os.path.join(PROJECT_DIR, output_file)
                        st.caption(f"📄 {full_path}")
                        with st.expander("結果を表示", expanded=True):
                            st.markdown(content)
                else:
                    files = list_output_files()
                    if files:
                        st.caption(f"📁 {os.path.join(PROJECT_DIR, 'output/')}")
                        st.markdown(f"**{len(files)} ファイル** が生成されました")
                        for fpath, fcontent in files:
                            ext = os.path.splitext(fpath)[1].lstrip(".")
                            lang = {
                                "tsx": "tsx", "ts": "typescript", "jsx": "jsx",
                                "js": "javascript", "css": "css", "json": "json",
                            }.get(ext, "")
                            with st.expander(f"📄 {fpath}"):
                                st.code(fcontent, language=lang)

        except subprocess.TimeoutExpired:
            stage_status[name].error(f"❌ {label} タイムアウト")
            log_area.error(f"{label} がタイムアウトしました（600秒）")
            st.session_state.error_msg = f"{label} がタイムアウト"
            error_occurred = True
            break
        except Exception as e:
            stage_status[name].error(f"❌ {label} エラー")
            log_area.error(f"{label} でエラー: {e}")
            st.session_state.error_msg = str(e)
            error_occurred = True
            break

    if not error_occurred:
        progress_bar.progress(1.0)
        log_area.empty()
        st.session_state.pipeline_done = True
        st.success("🎉 全工程が完了しました!")

        # 全出力ファイルのフルパス一覧
        st.markdown("### 出力ファイル一覧")
        for agent in AGENTS:
            if agent["output_file"]:
                fp = os.path.join(PROJECT_DIR, agent["output_file"])
                exists = "✅" if os.path.exists(fp) else "❌"
                st.markdown(f"- {exists} `{fp}`")
            else:
                fp = os.path.join(PROJECT_DIR, "output/")
                exists = "✅" if os.path.isdir(fp) else "❌"
                st.markdown(f"- {exists} `{fp}`")
                for fpath, _ in list_output_files():
                    st.markdown(f"  - `{fpath}`")

        # ZIPダウンロード + exports保存
        st.markdown("### 一括ダウンロード")
        zip_data = build_zip()
        if zip_data:
            export_path = save_to_exports(zip_data)
            st.info(f"📦 エクスポート保存: `{export_path}`")
            st.download_button(
                label="全ファイルをZIPでダウンロード",
                data=zip_data,
                file_name=os.path.basename(export_path),
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

    # エージェント実行ログ
    with st.expander("エージェント実行ログ（raw output）"):
        for name, output in st.session_state.all_outputs.items():
            agent_label = next(a["label"] for a in AGENTS if a["name"] == name)
            st.markdown(f"### {agent_label}")
            st.text(output[:5000] if len(output) > 5000 else output)
