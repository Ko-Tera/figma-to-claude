"""パイプラインオーケストレーター — 4エージェントの逐次実行を管理"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from typing import Callable

from .claude_client import ClaudeClient
from .figma_client import FigmaClient
from .agents import DesignerAgent, ArchitectAgent, CoderAgent, ReviewerAgent


@dataclass
class PipelineResult:
    """パイプライン全体の実行結果。"""
    figma_data: dict = field(default_factory=dict)
    design_analysis: dict = field(default_factory=dict)
    architecture: dict = field(default_factory=dict)
    generated_code: dict = field(default_factory=dict)
    review: dict = field(default_factory=dict)
    error: str | None = None
    current_stage: str = ""

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.review)

    def to_zip(self) -> bytes:
        """生成されたコードファイルをZIPにまとめる。"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in self.generated_code.get("files", []):
                path = f.get("path", "unknown.tsx")
                content = f.get("content", "")
                zf.writestr(path, content)

            # デザイン分析もJSONで同梱
            zf.writestr(
                "design-analysis.json",
                json.dumps(self.design_analysis, ensure_ascii=False, indent=2),
            )
            zf.writestr(
                "architecture.json",
                json.dumps(self.architecture, ensure_ascii=False, indent=2),
            )
            zf.writestr(
                "review.json",
                json.dumps(self.review, ensure_ascii=False, indent=2),
            )

        return buf.getvalue()


# ステージ定義
STAGES = [
    ("fetch", "Figmaデータ取得中..."),
    ("designer", "デザイナーが分析中..."),
    ("architect", "アーキテクトが設計中..."),
    ("coder", "コーダーがコード生成中..."),
    ("reviewer", "レビュアーが品質チェック中..."),
    ("done", "完了"),
]


class Pipeline:
    """4エージェントを逐次実行するパイプライン。"""

    def __init__(
        self,
        claude_client: ClaudeClient,
        figma_client: FigmaClient,
        on_progress: Callable[[str, str, float], None] | None = None,
    ):
        self.claude = claude_client
        self.figma = figma_client
        self.on_progress = on_progress or (lambda *_: None)

        self.designer = DesignerAgent(claude_client)
        self.architect = ArchitectAgent(claude_client)
        self.coder = CoderAgent(claude_client)
        self.reviewer = ReviewerAgent(claude_client)

    def _notify(self, stage: str, message: str, progress: float) -> None:
        """進捗コールバックを呼び出す。"""
        self.on_progress(stage, message, progress)

    def run(self, figma_url: str) -> PipelineResult:
        """パイプライン全体を実行する。

        Args:
            figma_url: FigmaファイルのURL

        Returns:
            PipelineResult
        """
        result = PipelineResult()

        try:
            # Stage 1: Figmaデータ取得
            result.current_stage = "fetch"
            self._notify("fetch", "Figmaからデザインデータを取得中...", 0.0)
            result.figma_data = self.figma.fetch_design_data(figma_url)
            self._notify("fetch", "デザインデータの取得完了", 0.2)

            # Stage 2: Designer Agent
            result.current_stage = "designer"
            self._notify("designer", "デザイナーがデザインを分析中...", 0.2)
            result.design_analysis = self.designer.run(result.figma_data)
            self._notify("designer", "デザイン分析完了", 0.4)

            # Stage 3: Architect Agent
            result.current_stage = "architect"
            self._notify("architect", "アーキテクトがコンポーネントを設計中...", 0.4)
            result.architecture = self.architect.run(result.design_analysis)
            self._notify("architect", "コンポーネント設計完了", 0.6)

            # Stage 4: Coder Agent
            result.current_stage = "coder"
            self._notify("coder", "コーダーがコードを生成中...", 0.6)
            result.generated_code = self.coder.run(
                result.architecture, result.design_analysis,
            )
            self._notify("coder", "コード生成完了", 0.8)

            # Stage 5: Reviewer Agent
            result.current_stage = "reviewer"
            self._notify("reviewer", "レビュアーが品質チェック中...", 0.8)
            result.review = self.reviewer.run(
                result.generated_code, result.design_analysis,
            )
            self._notify("done", "全工程完了!", 1.0)
            result.current_stage = "done"

        except Exception as e:
            result.error = f"[{result.current_stage}] {e}"
            self._notify("error", str(e), -1)

        return result
