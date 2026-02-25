"""Coder Agent（コーダー） — 設計書に基づきReact/Next.jsコードを生成"""

import json

from ..claude_client import ClaudeClient

SYSTEM_PROMPT = """\
あなたはシニアフロントエンドエンジニアです。
コンポーネント設計書とデザイン分析に基づいて、
本番品質のReact（Next.js）コードを生成します。

【あなたの仕事】
- 設計書の各コンポーネントに対して、完全なTSXコードを生成する
- Tailwind CSSでデザイントークンに忠実なスタイリングを適用する
- shadcn/uiコンポーネントを適切に活用する
- TypeScriptの型定義をPropsに含める
- Server/Client Componentsの使い分けを正しく実装する

【コーディング規約】
- "use client" ディレクティブはClient Componentsのみに記載
- export default で各コンポーネントをエクスポート
- Props型は interface で定義し、ComponentNameProps の命名規則を使用
- Tailwind CSSのクラスは cn() ユーティリティで結合
- アクセシビリティ属性（aria-label, role等）を適切に付与
- レスポンシブデザイン（sm: md: lg: プレフィックス）を実装

【出力ルール】
必ず以下のJSON構造のみを返してください。
{
  "files": [
    {
      "path": "src/components/ComponentName.tsx",
      "content": "完全なTSXコード文字列",
      "description": "ファイルの説明"
    }
  ],
  "dependencies": ["追加が必要なnpmパッケージ"],
  "setup_notes": "セットアップに関する補足（1〜2文）"
}
"""


class CoderAgent:
    """設計書に基づきコードを生成するコーダーエージェント。"""

    name = "Coder"
    description = "設計書からReact/Next.js + Tailwind CSSのコードを生成"

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    def run(self, architecture: dict, design_analysis: dict) -> dict:
        """設計書とデザイン分析からコードを生成する。

        Args:
            architecture: ArchitectAgent.run()の戻り値
            design_analysis: DesignerAgent.run()の戻り値

        Returns:
            生成されたコードファイル群（GeneratedCode）
        """
        user_message = self._build_prompt(architecture, design_analysis)
        return self.claude.generate_json(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=16384,
        )

    @staticmethod
    def _build_prompt(architecture: dict, design_analysis: dict) -> str:
        """設計書とデザイン分析からプロンプトを構築する。"""
        # デザイン分析から必要な部分だけ抽出
        design_context = {
            "color_palette": design_analysis.get("color_palette", {}),
            "typography": design_analysis.get("typography", []),
            "spacing": design_analysis.get("spacing", {}),
            "layout": design_analysis.get("layout", {}),
        }

        return f"""\
以下のコンポーネント設計書とデザイントークンに基づいて、
本番品質のReact/Next.jsコードを生成してください。

【コンポーネント設計書】
{json.dumps(architecture, ensure_ascii=False, indent=2)}

【デザイントークン】
{json.dumps(design_context, ensure_ascii=False, indent=2)}

設計書に含まれる全コンポーネントのTSXコードを生成してください。
各コンポーネントは完全に動作する状態で出力すること。
"""
