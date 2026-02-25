"""Figma → Claude Code ランチャー

Figma URL または デザイン画像を入力すると、4つのエージェントを順番に実行し、
デザイン分析 → 設計 → コード生成 → レビューまでを自動で行う。
"""

import io
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime

# このスクリプトがあるディレクトリ = プロジェクトルート
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(PROJECT_DIR, "exports")


def run_agent(agent_name: str, prompt: str) -> str:
    """Claude Code CLIを使ってエージェントを実行する。"""
    cmd = [
        "claude",
        "--print",
        "--agent", agent_name,
        "--dangerously-skip-permissions",
        prompt,
    ]
    result = subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Agent '{agent_name}' failed:\n{result.stderr or result.stdout}"
        )
    return result.stdout


def build_designer_prompt(source: str) -> str:
    """入力ソースに応じてDesignerエージェント用プロンプトを構築する。"""
    if source.startswith("http"):
        return f"以下のFigma URLのデザインを分析して design-analysis.md を作成してください:\n{source}"

    # ファイルパス（カンマ区切りで複数可）
    paths = [p.strip() for p in source.split(",")]
    abs_paths = []
    for p in paths:
        ap = os.path.abspath(p)
        if not os.path.exists(ap):
            print(f"警告: ファイルが見つかりません: {ap}")
            continue
        abs_paths.append(ap)

    if not abs_paths:
        print("エラー: 有効なファイルが見つかりません")
        sys.exit(1)

    paths_str = "\n".join(f"- {p}" for p in abs_paths)
    return (
        f"以下のデザイン画像ファイルを Read ツールで読み込んで分析し、design-analysis.md を作成してください。\n"
        f"画像ファイル:\n{paths_str}"
    )


def run_pipeline(source: str) -> dict:
    """4エージェントのパイプラインを順番に実行する。"""
    results = {}

    # Stage 1: Designer
    print("\n[1/4] Designer -- analyzing design...")
    results["designer"] = run_agent("designer", build_designer_prompt(source))
    print("  done: design-analysis.md")

    # Stage 2: Architect
    print("\n[2/4] Architect -- designing components...")
    results["architect"] = run_agent(
        "architect",
        "design-analysis.md を読み込んで architecture.md を作成してください。",
    )
    print("  done: architecture.md")

    # Stage 3: Coder
    print("\n[3/4] Coder -- generating code...")
    results["coder"] = run_agent(
        "coder",
        "architecture.md と design-analysis.md を読み込んで output/ ディレクトリにコードを生成してください。",
    )
    print("  done: output/")

    # Stage 4: Reviewer
    print("\n[4/4] Reviewer -- reviewing code...")
    results["reviewer"] = run_agent(
        "reviewer",
        "output/ のコードを design-analysis.md と照合してレビューし、問題があれば修正してください。review.md を作成してください。",
    )
    print("  done: review.md")

    return results


def build_zip() -> bytes | None:
    """全出力ファイルを1つのZIPにまとめて返す。"""
    buf = io.BytesIO()
    file_count = 0

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ["design-analysis.md", "architecture.md", "review.md"]:
            path = os.path.join(PROJECT_DIR, name)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    zf.writestr(name, f.read())
                file_count += 1

        output_dir = os.path.join(PROJECT_DIR, "output")
        if os.path.isdir(output_dir):
            for root, _, names in os.walk(output_dir):
                for fname in names:
                    full = os.path.join(root, fname)
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


def save_to_exports(zip_data: bytes) -> str:
    """ZIPデータをexports/にタイムスタンプ付きで保存し、フルパスを返す。"""
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"figma-output_{timestamp}.zip"
    filepath = os.path.join(EXPORTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(zip_data)
    return filepath


def main():
    """CLIエントリポイント。"""
    if len(sys.argv) < 2:
        print("使い方:")
        print("  python launcher.py <Figma URL>")
        print("  python launcher.py <画像パス>")
        print("  python launcher.py <画像1>,<画像2>,<画像3>  (複数画像)")
        print()
        print("例:")
        print("  python launcher.py https://www.figma.com/design/XXXXX/...")
        print("  python launcher.py ./design.png")
        print("  python launcher.py ./top.png,./about.png,./footer.png")
        sys.exit(1)

    source = sys.argv[1]

    # claude CLI が使えるか確認
    if not shutil.which("claude"):
        print("エラー: claude CLI が見つかりません。")
        print("  npm install -g @anthropic-ai/claude-code")
        sys.exit(1)

    is_url = source.startswith("http")
    print("=" * 50)
    print("Figma → Claude Code パイプライン")
    print("=" * 50)
    print(f"入力: {'URL' if is_url else '画像ファイル'}")
    print(f"ソース: {source}")

    try:
        run_pipeline(source)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

    # exports/ に ZIP を保存
    zip_data = build_zip()
    if zip_data:
        export_path = save_to_exports(zip_data)
        print(f"\nExported: {export_path}")

    print("\n" + "=" * 50)
    print("All steps completed.")
    print("=" * 50)
    print(f"  design-analysis.md  -- design analysis")
    print(f"  architecture.md     -- architecture")
    print(f"  output/             -- generated code")
    print(f"  review.md           -- review")
    if zip_data:
        print(f"  {export_path}  -- zip archive")


if __name__ == "__main__":
    main()
