"""Figma → Claude Code ランチャー

Figma URLを入力すると、4つのエージェントを順番に実行し、
デザイン分析 → 設計 → コード生成 → レビューまでを自動で行う。
"""

import json
import os
import shutil
import subprocess
import sys

# このスクリプトがあるディレクトリ = プロジェクトルート
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


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


def run_pipeline(figma_url: str) -> dict:
    """4エージェントのパイプラインを順番に実行する。"""
    results = {}

    # Stage 1: Designer
    print("\n[1/4] 🎨 Designer — Figmaデザインを分析中...")
    results["designer"] = run_agent(
        "designer",
        f"以下のFigma URLのデザインを分析して design-analysis.md を作成してください:\n{figma_url}",
    )
    print("  ✅ design-analysis.md を作成しました")

    # Stage 2: Architect
    print("\n[2/4] 🏗️ Architect — コンポーネントを設計中...")
    results["architect"] = run_agent(
        "architect",
        "design-analysis.md を読み込んで architecture.md を作成してください。",
    )
    print("  ✅ architecture.md を作成しました")

    # Stage 3: Coder
    print("\n[3/4] 💻 Coder — コードを生成中...")
    results["coder"] = run_agent(
        "coder",
        "architecture.md と design-analysis.md を読み込んで output/ ディレクトリにコードを生成してください。",
    )
    print("  ✅ output/ にコードを生成しました")

    # Stage 4: Reviewer
    print("\n[4/4] 🔍 Reviewer — コードをレビュー中...")
    results["reviewer"] = run_agent(
        "reviewer",
        "output/ のコードを design-analysis.md と照合してレビューし、問題があれば修正してください。review.md を作成してください。",
    )
    print("  ✅ review.md を作成しました")

    return results


def main():
    """CLIエントリポイント。"""
    if len(sys.argv) < 2:
        print("使い方: python launcher.py <Figma URL>")
        print("例: python launcher.py https://www.figma.com/design/XXXXX/...")
        sys.exit(1)

    figma_url = sys.argv[1]

    # claude CLI が使えるか確認
    if not shutil.which("claude"):
        print("エラー: claude CLI が見つかりません。")
        print("  npm install -g @anthropic-ai/claude-code")
        sys.exit(1)

    print("=" * 50)
    print("Figma → Claude Code パイプライン")
    print("=" * 50)
    print(f"URL: {figma_url}")

    try:
        run_pipeline(figma_url)
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("🎉 全工程完了!")
    print("=" * 50)
    print(f"  📄 design-analysis.md — デザイン分析")
    print(f"  📄 architecture.md    — 設計書")
    print(f"  📁 output/            — 生成コード")
    print(f"  📄 review.md          — レビュー結果")


if __name__ == "__main__":
    main()
