"""Reviewer Agent（レビュアー） — 生成コードの品質レビューとデザイン忠実度チェック"""

import json

from ..claude_client import ClaudeClient

SYSTEM_PROMPT = """\
あなたはシニアコードレビュアー兼QAエンジニアです。
生成されたReactコードをデザイン分析と照合し、
品質・アクセシビリティ・デザイン忠実度を評価します。

【あなたの仕事】
- コード品質チェック（TypeScript型安全性、命名規則、構造）
- デザイン忠実度チェック（カラー・フォント・スペーシングの一致度）
- アクセシビリティチェック（WCAG 2.1 AA基準）
- レスポンシブデザインチェック
- パフォーマンス考慮点の確認
- 改善提案の提示

【評価基準】
- score: 0〜100の総合スコア
- 80以上: 承認（approved: true）
- 80未満: 要改善（approved: false）

【出力ルール】
必ず以下のJSON構造のみを返してください。
{
  "score": 85,
  "approved": true,
  "summary": "レビュー結果の要約（2〜3文）",
  "categories": {
    "code_quality": {
      "score": 90,
      "notes": "評価コメント"
    },
    "design_fidelity": {
      "score": 85,
      "notes": "評価コメント"
    },
    "accessibility": {
      "score": 80,
      "notes": "評価コメント"
    },
    "responsiveness": {
      "score": 85,
      "notes": "評価コメント"
    }
  },
  "issues": [
    {
      "severity": "critical | warning | info",
      "file": "該当ファイルパス",
      "description": "問題の説明",
      "suggestion": "改善案"
    }
  ],
  "improvements": [
    "改善提案1",
    "改善提案2"
  ]
}
"""


class ReviewerAgent:
    """生成コードをレビューするレビュアーエージェント。"""

    name = "Reviewer"
    description = "生成コードの品質・アクセシビリティ・デザイン忠実度をレビュー"

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    def run(self, generated_code: dict, design_analysis: dict) -> dict:
        """生成コードをレビューする。

        Args:
            generated_code: CoderAgent.run()の戻り値
            design_analysis: DesignerAgent.run()の戻り値

        Returns:
            レビュー結果（ReviewResult）
        """
        user_message = self._build_prompt(generated_code, design_analysis)
        return self.claude.generate_json(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )

    @staticmethod
    def _build_prompt(generated_code: dict, design_analysis: dict) -> str:
        """コードとデザイン分析からプロンプトを構築する。"""
        # コードファイル一覧
        files_summary = []
        for f in generated_code.get("files", []):
            files_summary.append({
                "path": f.get("path", ""),
                "content": f.get("content", ""),
            })

        # デザイン分析の要約
        design_context = {
            "color_palette": design_analysis.get("color_palette", {}),
            "typography": design_analysis.get("typography", []),
            "components": [
                c.get("name", "") for c in design_analysis.get("components", [])
            ],
        }

        return f"""\
以下の生成コードをレビューしてください。

【生成コード】
{json.dumps(files_summary, ensure_ascii=False, indent=2)}

【元のデザイン分析】
{json.dumps(design_context, ensure_ascii=False, indent=2)}

コード品質・デザイン忠実度・アクセシビリティ・レスポンシブ対応を
総合的に評価してください。
"""
