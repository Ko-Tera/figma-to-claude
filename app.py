"""Figma to Claude Code — Streamlit UI

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


# ---------- ヘルパー関数 ----------
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
                files.append((full, "(binary)"))
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
        da = read_file_safe("design-analysis.md")
        if da:
            zf.writestr("design-analysis.md", da)
            file_count += 1

        arch = read_file_safe("architecture.md")
        if arch:
            zf.writestr("architecture.md", arch)
            file_count += 1

        rev = read_file_safe("review.md")
        if rev:
            zf.writestr("review.md", rev)
            file_count += 1

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


# ---------- エージェント定義 ----------
AGENTS = [
    {
        "name": "designer",
        "label": "Designer",
        "desc": "デザイン分析",
        "output_file": "design-analysis.md",
    },
    {
        "name": "architect",
        "label": "Architect",
        "desc": "コンポーネント設計",
        "prompt": "design-analysis.md を読み込んで architecture.md を作成してください。",
        "output_file": "architecture.md",
    },
    {
        "name": "coder",
        "label": "Coder",
        "desc": "コード生成",
        "prompt": "architecture.md と design-analysis.md を読み込んで output/ ディレクトリにコードを生成してください。",
        "output_file": None,
    },
    {
        "name": "reviewer",
        "label": "Reviewer",
        "desc": "レビュー + 自動修正",
        "prompt": "output/ のコードを design-analysis.md と照合してレビューし、問題があれば修正してください。review.md を作成してください。",
        "output_file": "review.md",
    },
]

MODEL = "opus"

# ---------- ページ設定 ----------
st.set_page_config(
    page_title="Figma to Code",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------- カスタムCSS ----------
st.markdown("""
<style>
    /* 全体 */
    .stApp {
        background-color: #ffffff;
    }
    .block-container {
        max-width: 720px;
        padding-top: 3rem;
        padding-bottom: 4rem;
    }

    /* ヘッダー */
    h1 {
        font-weight: 600 !important;
        font-size: 1.6rem !important;
        letter-spacing: -0.02em;
        color: #1a1a1a !important;
    }

    /* サブテキスト */
    .subtle {
        color: #8c8c8c;
        font-size: 0.85rem;
        margin-bottom: 2rem;
    }

    /* ステップインジケーター */
    .steps {
        display: flex;
        gap: 0;
        margin: 1.5rem 0;
        align-items: center;
    }
    .step {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        color: #b0b0b0;
        transition: color 0.2s;
    }
    .step.active {
        color: #1a1a1a;
        font-weight: 500;
    }
    .step.done {
        color: #10b981;
    }
    .step-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #e0e0e0;
        flex-shrink: 0;
    }
    .step.active .step-dot {
        background: #1a1a1a;
        box-shadow: 0 0 0 3px rgba(26,26,26,0.1);
    }
    .step.done .step-dot {
        background: #10b981;
    }
    .step-line {
        width: 24px;
        height: 1px;
        background: #e5e5e5;
        margin: 0 8px;
        flex-shrink: 0;
    }

    /* ボタン */
    .stButton > button[kind="primary"] {
        background-color: #1a1a1a !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.55rem 1.5rem !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        transition: background 0.15s;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #333333 !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: transparent !important;
        color: #666666 !important;
        border: 1px solid #e5e5e5 !important;
        border-radius: 8px !important;
        padding: 0.55rem 1.5rem !important;
        font-weight: 400 !important;
        font-size: 0.85rem !important;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: #cccccc !important;
        color: #1a1a1a !important;
    }

    /* 入力フィールド */
    .stTextInput > div > div > input {
        border: 1px solid #e5e5e5 !important;
        border-radius: 8px !important;
        padding: 0.6rem 0.9rem !important;
        font-size: 0.85rem !important;
        background: #fafafa !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #1a1a1a !important;
        box-shadow: none !important;
        background: #ffffff !important;
    }

    /* ラジオ */
    .stRadio > div {
        gap: 0.5rem;
    }

    /* Expander */
    .streamlit-expanderHeader {
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        color: #444444 !important;
    }

    /* ファイルアップローダー */
    .stFileUploader > div > div {
        border: 1px dashed #d5d5d5 !important;
        border-radius: 8px !important;
        background: #fafafa !important;
    }

    /* 結果カード */
    .result-card {
        border: 1px solid #f0f0f0;
        border-radius: 10px;
        padding: 1.2rem 1.4rem;
        margin: 0.6rem 0;
        background: #fafafa;
    }
    .result-card h4 {
        margin: 0 0 0.4rem 0;
        font-size: 0.85rem;
        font-weight: 600;
        color: #1a1a1a;
    }
    .result-card .path {
        font-size: 0.75rem;
        color: #999;
        font-family: 'SF Mono', 'Menlo', monospace;
    }

    /* プログレス */
    .stProgress > div > div > div {
        background-color: #1a1a1a !important;
    }

    /* サイドバー */
    section[data-testid="stSidebar"] {
        background-color: #fafafa;
        border-right: 1px solid #f0f0f0;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    /* divider */
    hr {
        border-color: #f0f0f0 !important;
    }

    /* download button */
    .stDownloadButton > button {
        background-color: transparent !important;
        color: #1a1a1a !important;
        border: 1px solid #e5e5e5 !important;
        border-radius: 8px !important;
        font-size: 0.8rem !important;
        font-weight: 400 !important;
    }
    .stDownloadButton > button:hover {
        border-color: #1a1a1a !important;
    }

    /* 成功メッセージ */
    .stSuccess {
        background-color: #f0fdf4 !important;
        border: 1px solid #bbf7d0 !important;
        color: #166534 !important;
        border-radius: 8px !important;
    }

    /* info */
    .stInfo {
        background-color: #f8f9fa !important;
        border: 1px solid #e9ecef !important;
        color: #495057 !important;
        border-radius: 8px !important;
    }

    /* ラベル非表示 */
    .stRadio > label, .stTextInput > label, .stFileUploader > label {
        font-size: 0.8rem !important;
        color: #888 !important;
        font-weight: 400 !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------- セッションステート初期化 ----------
if "pipeline_done" not in st.session_state:
    st.session_state.pipeline_done = False
if "all_outputs" not in st.session_state:
    st.session_state.all_outputs = {}
if "error_msg" not in st.session_state:
    st.session_state.error_msg = None

# ---------- ヘッダー ----------
st.markdown("# Figma to Code")
st.markdown('<p class="subtle">Figma URL or design images &rarr; production-ready code, automatically.</p>', unsafe_allow_html=True)

# ---------- サイドバー（最小限） ----------
with st.sidebar:
    st.markdown("#### Exports")
    exports = list_exports()
    if exports:
        for fname, fpath in exports:
            with open(fpath, "rb") as f:
                st.download_button(
                    label=fname,
                    data=f.read(),
                    file_name=fname,
                    mime="application/zip",
                    key=f"export_{fname}",
                    use_container_width=True,
                )
    else:
        st.caption("No exports yet.")

# ---------- claude CLI チェック ----------
if not shutil.which("claude"):
    st.error("claude CLI not found. Run `npm install -g @anthropic-ai/claude-code`")
    st.stop()

# ---------- パイプラインステップ表示 ----------
def render_steps(current: int = -1, done_count: int = 0):
    """ステップインジケーターをレンダリングする。"""
    parts = []
    for i, agent in enumerate(AGENTS):
        cls = "step"
        if i < done_count:
            cls += " done"
        elif i == current:
            cls += " active"
        parts.append(f'<div class="{cls}"><span class="step-dot"></span>{agent["label"]}</div>')
        if i < len(AGENTS) - 1:
            parts.append('<div class="step-line"></div>')
    return f'<div class="steps">{"".join(parts)}</div>'

st.markdown(render_steps(), unsafe_allow_html=True)

# ---------- 入力 ----------
input_mode = st.radio(
    "Input",
    ["Figma URL", "Image Upload"],
    horizontal=True,
    label_visibility="collapsed",
)

figma_url = None
uploaded_images = None
image_paths = None

if input_mode == "Figma URL":
    figma_url = st.text_input(
        "Figma URL",
        placeholder="https://www.figma.com/design/...",
        label_visibility="collapsed",
    )
    has_input = bool(figma_url)
else:
    uploaded_images = st.file_uploader(
        "Upload images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    has_input = bool(uploaded_images)

    if uploaded_images:
        cols = st.columns(min(len(uploaded_images), 4))
        for i, img in enumerate(uploaded_images):
            with cols[i % 4]:
                st.image(img, caption=img.name, use_container_width=True)

# ---------- アクションボタン ----------
st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
col1, col2 = st.columns([2, 1])

with col1:
    auto_run = st.button(
        "Generate Code",
        disabled=not has_input,
        type="primary",
        use_container_width=True,
    )

with col2:
    interactive_run = st.button(
        "Open in Terminal",
        disabled=not has_input,
        type="secondary",
        use_container_width=True,
    )

# ---------- 画像の保存（実行時） ----------
if (auto_run or interactive_run) and uploaded_images:
    image_paths = save_uploaded_images(uploaded_images)

# ---------- 対話モード ----------
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
    st.success("Claude Code launched in Terminal.")

# ---------- 自動パイプライン実行 ----------
if auto_run and has_input:
    st.session_state.pipeline_done = False
    st.session_state.all_outputs = {}
    st.session_state.error_msg = None

    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

    progress_bar = st.progress(0.0)
    status_text = st.empty()
    step_display = st.empty()

    results_container = st.container()
    error_occurred = False

    for i, agent in enumerate(AGENTS):
        name = agent["name"]
        label = agent["label"]
        output_file = agent["output_file"]

        # ステップ表示更新
        step_display.markdown(render_steps(current=i, done_count=i), unsafe_allow_html=True)
        progress_bar.progress(i / 4)
        status_text.markdown(f"<p style='color:#888; font-size:0.8rem;'>Running {label}...</p>", unsafe_allow_html=True)

        # プロンプト構築
        if name == "designer":
            prompt = build_designer_prompt(figma_url, image_paths)
        else:
            prompt = agent["prompt"]

        try:
            stdout, stderr = run_claude_agent(name, prompt, MODEL)
            st.session_state.all_outputs[name] = stdout

            # 完了した結果を即座に表示
            with results_container:
                if output_file:
                    content = read_file_safe(output_file)
                    if content:
                        full_path = os.path.join(PROJECT_DIR, output_file)
                        st.markdown(
                            f'<div class="result-card">'
                            f'<h4>{label}</h4>'
                            f'<p class="path">{full_path}</p>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        with st.expander(f"{label} output", expanded=False):
                            st.markdown(content)
                else:
                    files = list_output_files()
                    if files:
                        st.markdown(
                            f'<div class="result-card">'
                            f'<h4>{label}</h4>'
                            f'<p class="path">{os.path.join(PROJECT_DIR, "output/")} &mdash; {len(files)} files</p>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        for fpath, fcontent in files:
                            ext = os.path.splitext(fpath)[1].lstrip(".")
                            lang = {
                                "tsx": "tsx", "ts": "typescript", "jsx": "jsx",
                                "js": "javascript", "css": "css", "json": "json",
                            }.get(ext, "")
                            with st.expander(os.path.basename(fpath)):
                                st.code(fcontent, language=lang)

        except subprocess.TimeoutExpired:
            status_text.markdown(f"<p style='color:#dc2626; font-size:0.8rem;'>{label} timed out (600s)</p>", unsafe_allow_html=True)
            st.session_state.error_msg = f"{label} timed out"
            error_occurred = True
            break
        except Exception as e:
            status_text.markdown(f"<p style='color:#dc2626; font-size:0.8rem;'>{label}: {e}</p>", unsafe_allow_html=True)
            st.session_state.error_msg = str(e)
            error_occurred = True
            break

    if not error_occurred:
        progress_bar.progress(1.0)
        step_display.markdown(render_steps(current=-1, done_count=4), unsafe_allow_html=True)
        status_text.empty()
        st.session_state.pipeline_done = True

        st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
        st.success("All steps completed.")

        # ZIP + exports
        zip_data = build_zip()
        if zip_data:
            export_path = save_to_exports(zip_data)
            st.markdown(f"<p style='color:#888; font-size:0.75rem;'>Saved to {export_path}</p>", unsafe_allow_html=True)
            st.download_button(
                label="Download all as ZIP",
                data=zip_data,
                file_name=os.path.basename(export_path),
                mime="application/zip",
                use_container_width=True,
            )

    # raw log
    with st.expander("Raw agent output"):
        for name, output in st.session_state.all_outputs.items():
            agent_label = next(a["label"] for a in AGENTS if a["name"] == name)
            st.markdown(f"**{agent_label}**")
            st.text(output[:5000] if len(output) > 5000 else output)
