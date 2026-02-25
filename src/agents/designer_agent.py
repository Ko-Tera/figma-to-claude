"""Designer Agent（デザイナー） — Figmaデザインデータを分析し、構造化されたデザイン分析を出力"""

import json

from ..claude_client import ClaudeClient

SYSTEM_PROMPT = """\
あなたはシニアUIデザイナーです。
Figmaから抽出された生のデザインデータを分析し、
フロントエンド開発に必要な構造化されたデザイン分析を出力します。

【あなたの仕事】
- カラーパレットをプライマリ/セカンダリ/背景/テキスト/アクセントに分類する
- タイポグラフィスケール（見出し/本文/キャプション）を定義する
- スペーシングシステム（余白・パディングの規則性）を分析する
- レイアウトパターン（グリッド/フレックス/スタック）を特定する
- コンポーネント一覧を階層構造で整理する

【出力ルール】
必ず以下のJSON構造のみを返してください。余計な説明は不要です。
{
  "design_summary": "デザイン全体の概要（1〜2文）",
  "color_palette": {
    "primary": "#hex",
    "secondary": "#hex",
    "background": "#hex",
    "text": "#hex",
    "accent": "#hex",
    "additional": ["#hex", ...]
  },
  "typography": [
    {
      "role": "heading-1 | heading-2 | heading-3 | body | caption | label",
      "font_family": "フォント名",
      "font_size": "px値",
      "font_weight": 400,
      "line_height": "px値またはem値"
    }
  ],
  "spacing": {
    "unit": 4,
    "scale": [4, 8, 12, 16, 24, 32, 48, 64]
  },
  "layout": {
    "type": "grid | flex | stack | mixed",
    "max_width": "px値",
    "columns": 12,
    "gutter": "px値",
    "breakpoints": {
      "mobile": 375,
      "tablet": 768,
      "desktop": 1280
    }
  },
  "components": [
    {
      "name": "コンポーネント名",
      "type": "navigation | hero | card | form | footer | button | modal | list | section",
      "description": "コンポーネントの説明",
      "children": ["子コンポーネント名"]
    }
  ]
}
"""


class DesignerAgent:
    """Figmaデザインデータを分析するデザイナーエージェント。"""

    name = "Designer"
    description = "Figmaデザインを分析し、デザイントークンとコンポーネント構成を抽出"

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    def run(self, figma_data: dict) -> dict:
        """Figmaデザインデータからデザイン分析を生成する。

        Args:
            figma_data: FigmaClient.fetch_design_data()の戻り値

        Returns:
            構造化されたデザイン分析（DesignAnalysis）
        """
        user_message = self._build_prompt(figma_data)
        return self.claude.generate_json(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )

    @staticmethod
    def _build_prompt(figma_data: dict) -> str:
        """Figmaデータからプロンプトを構築する。"""
        name = figma_data.get("name", "不明")
        colors = figma_data.get("colors", [])
        fonts = figma_data.get("fonts", [])
        components = figma_data.get("components", [])

        # コンポーネントは上位30件に制限（トークン節約）
        top_components = components[:30]

        return f"""\
以下のFigmaデザインデータを分析してください。

【ファイル名】
{name}

【使用カラー】
{json.dumps(colors, ensure_ascii=False, indent=2)}

【使用フォント】
{json.dumps(fonts, ensure_ascii=False, indent=2)}

【コンポーネント構成】（上位{len(top_components)}件）
{json.dumps(top_components, ensure_ascii=False, indent=2)}

上記データに基づいて、構造化されたデザイン分析を出力してください。
"""
