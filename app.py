"""Figma to Claude Code — Streamlit UI"""

import json
import os

import streamlit as st
from dotenv import load_dotenv

from src.claude_client import ClaudeClient
from src.figma_client import FigmaClient
from src.pipeline import Pipeline, PipelineResult, STAGES

load_dotenv()

# ---------- ページ設定 ----------
st.set_page_config(
    page_title="Figma → Claude Code",
    page_icon="🎨",
    layout="wide",
)

# ---------- カスタムCSS ----------
st.markdown("""
<style>
.agent-card {
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0;
    background: #fafafa;
}
.agent-card.active {
    border-color: #6366f1;
    background: #eef2ff;
}
.agent-card.done {
    border-color: #22c55e;
    background: #f0fdf4;
}
.stage-indicator {
    display: flex;
    justify-content: space-between;
    margin: 20px 0;
}
</style>
""", unsafe_allow_html=True)

# ---------- ヘッダー ----------
st.title("Figma → Claude Code")
st.caption("Figmaデザインを4つのAIエージェントで解析し、本番品質のコードを自動生成")

# ---------- サイドバー: 設定 ----------
with st.sidebar:
    st.header("設定")

    anthropic_key = st.text_input(
        "Anthropic API Key",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Claude APIのキー（sk-ant-...）",
    )
    figma_token = st.text_input(
        "Figma Access Token",
        value=os.environ.get("FIGMA_ACCESS_TOKEN", ""),
        type="password",
        help="Figmaのパーソナルアクセストークン",
    )
    model = st.selectbox(
        "Claude Model",
        ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
        index=0,
        help="使用するClaudeモデル",
    )

    st.divider()
    st.markdown("### エージェント一覧")
    agents_info = [
        ("🎨 Designer", "Figmaデザインを分析"),
        ("🏗️ Architect", "コンポーネントを設計"),
        ("💻 Coder", "コードを生成"),
        ("🔍 Reviewer", "品質をレビュー"),
    ]
    for name, desc in agents_info:
        st.markdown(f"**{name}**  \n{desc}")

# ---------- メイン: URL入力 ----------
figma_url = st.text_input(
    "Figma URL",
    placeholder="https://www.figma.com/design/XXXXX/...",
    help="FigmaファイルまたはフレームのURLを入力",
)

# ---------- 実行ボタン ----------
can_run = bool(figma_url and anthropic_key and figma_token)

if not can_run:
    if not anthropic_key:
        st.warning("サイドバーでAnthropic API Keyを設定してください")
    if not figma_token:
        st.warning("サイドバーでFigma Access Tokenを設定してください")

if st.button("コード生成を開始", disabled=not can_run, type="primary", use_container_width=True):
    # 進捗表示用
    progress_bar = st.progress(0.0)
    status_text = st.empty()
    stage_cols = st.columns(5)
    stage_placeholders = {}
    for i, (stage_id, stage_label) in enumerate(STAGES[:-1]):
        with stage_cols[i]:
            stage_placeholders[stage_id] = st.empty()
            stage_placeholders[stage_id].info(f"⏳ {stage_label.replace('...', '')}")

    def on_progress(stage: str, message: str, progress: float) -> None:
        if progress >= 0:
            progress_bar.progress(progress)
        status_text.markdown(f"**{message}**")

        # ステージ表示を更新
        stage_order = [s[0] for s in STAGES[:-1]]
        if stage in stage_order:
            idx = stage_order.index(stage)
            # 完了したステージを緑にする
            for i in range(idx):
                sid = stage_order[i]
                if sid in stage_placeholders:
                    stage_placeholders[sid].success(f"✅ {STAGES[i][1].replace('...', '')}")
            # 現在のステージ
            if stage in stage_placeholders:
                if progress >= (idx + 1) / 5:
                    stage_placeholders[stage].success(f"✅ {STAGES[stage_order.index(stage)][1].replace('...', '')}")
                else:
                    stage_placeholders[stage].warning(f"⚙️ {message}")

    # パイプライン実行
    try:
        claude = ClaudeClient(api_key=anthropic_key, model=model)
        figma = FigmaClient(access_token=figma_token)
        pipeline = Pipeline(claude, figma, on_progress=on_progress)

        result: PipelineResult = pipeline.run(figma_url)

        if result.error:
            st.error(f"エラーが発生しました: {result.error}")
        else:
            st.success("全工程が完了しました!")

            # ---------- 結果表示（タブ） ----------
            tab_design, tab_arch, tab_code, tab_review = st.tabs([
                "🎨 デザイン分析",
                "🏗️ 設計書",
                "💻 生成コード",
                "🔍 レビュー結果",
            ])

            with tab_design:
                st.subheader("デザイン分析結果")
                if result.design_analysis:
                    summary = result.design_analysis.get("design_summary", "")
                    if summary:
                        st.markdown(f"> {summary}")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### カラーパレット")
                        palette = result.design_analysis.get("color_palette", {})
                        for name, color in palette.items():
                            if isinstance(color, str):
                                st.markdown(f"- **{name}**: `{color}`")
                            elif isinstance(color, list):
                                st.markdown(f"- **{name}**: {', '.join(f'`{c}`' for c in color)}")

                    with col2:
                        st.markdown("#### タイポグラフィ")
                        for t in result.design_analysis.get("typography", []):
                            st.markdown(
                                f"- **{t.get('role', '')}**: "
                                f"{t.get('font_family', '')} "
                                f"{t.get('font_size', '')}px / "
                                f"weight {t.get('font_weight', '')}"
                            )

                    st.markdown("#### コンポーネント一覧")
                    for c in result.design_analysis.get("components", []):
                        children = c.get("children", [])
                        children_str = f" → {', '.join(children)}" if children else ""
                        st.markdown(f"- **{c.get('name', '')}** ({c.get('type', '')}){children_str}")

                    with st.expander("生データ（JSON）"):
                        st.json(result.design_analysis)

            with tab_arch:
                st.subheader("コンポーネント設計書")
                if result.architecture:
                    st.markdown("#### ファイル構成")
                    for f in result.architecture.get("file_structure", []):
                        st.markdown(f"- `{f.get('path', '')}` — {f.get('description', '')}")

                    st.markdown("#### コンポーネント定義")
                    for comp in result.architecture.get("components", []):
                        with st.expander(f"📦 {comp.get('name', '')} ({comp.get('type', 'server')})"):
                            st.markdown(f"**説明**: {comp.get('description', '')}")
                            st.markdown(f"**ファイル**: `{comp.get('file_path', '')}`")

                            props = comp.get("props", [])
                            if props:
                                st.markdown("**Props:**")
                                for p in props:
                                    req = "必須" if p.get("required") else "任意"
                                    st.markdown(
                                        f"- `{p.get('name', '')}`: "
                                        f"`{p.get('type', '')}` ({req}) — "
                                        f"{p.get('description', '')}"
                                    )

                            shadcn = comp.get("shadcn_components", [])
                            if shadcn:
                                st.markdown(f"**shadcn/ui**: {', '.join(shadcn)}")

                    with st.expander("生データ（JSON）"):
                        st.json(result.architecture)

            with tab_code:
                st.subheader("生成コード")
                if result.generated_code:
                    files = result.generated_code.get("files", [])
                    st.markdown(f"**{len(files)}ファイル** が生成されました")

                    deps = result.generated_code.get("dependencies", [])
                    if deps:
                        st.markdown(f"**追加パッケージ**: {', '.join(f'`{d}`' for d in deps)}")

                    notes = result.generated_code.get("setup_notes", "")
                    if notes:
                        st.info(notes)

                    for f in files:
                        with st.expander(f"📄 {f.get('path', '')}"):
                            st.code(f.get("content", ""), language="tsx")

                    # ZIPダウンロード
                    zip_data = result.to_zip()
                    st.download_button(
                        label="ZIPでダウンロード",
                        data=zip_data,
                        file_name="generated-code.zip",
                        mime="application/zip",
                        type="primary",
                        use_container_width=True,
                    )

            with tab_review:
                st.subheader("レビュー結果")
                if result.review:
                    score = result.review.get("score", 0)
                    approved = result.review.get("approved", False)

                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.metric("総合スコア", f"{score}/100")
                        if approved:
                            st.success("承認")
                        else:
                            st.warning("要改善")
                    with col2:
                        st.markdown(result.review.get("summary", ""))

                    st.markdown("#### カテゴリ別評価")
                    cats = result.review.get("categories", {})
                    cat_cols = st.columns(len(cats) if cats else 1)
                    for i, (cat_name, cat_data) in enumerate(cats.items()):
                        with cat_cols[i]:
                            label = {
                                "code_quality": "コード品質",
                                "design_fidelity": "デザイン忠実度",
                                "accessibility": "アクセシビリティ",
                                "responsiveness": "レスポンシブ",
                            }.get(cat_name, cat_name)
                            st.metric(label, f"{cat_data.get('score', 0)}/100")
                            st.caption(cat_data.get("notes", ""))

                    issues = result.review.get("issues", [])
                    if issues:
                        st.markdown("#### 指摘事項")
                        for issue in issues:
                            severity = issue.get("severity", "info")
                            icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")
                            st.markdown(
                                f"{icon} **[{severity}]** `{issue.get('file', '')}`  \n"
                                f"{issue.get('description', '')}  \n"
                                f"💡 {issue.get('suggestion', '')}"
                            )

                    improvements = result.review.get("improvements", [])
                    if improvements:
                        st.markdown("#### 改善提案")
                        for imp in improvements:
                            st.markdown(f"- {imp}")

                    with st.expander("生データ（JSON）"):
                        st.json(result.review)

    except Exception as e:
        st.error(f"実行エラー: {e}")
