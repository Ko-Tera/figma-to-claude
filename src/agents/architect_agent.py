"""Architect Agent（アーキテクト） — デザイン分析からコンポーネント設計書を作成"""

import json

from ..claude_client import ClaudeClient

SYSTEM_PROMPT = """\
あなたはシニアフロントエンドアーキテクトです。
デザイン分析データに基づいて、React（Next.js App Router）の
コンポーネント設計書を作成します。

【あなたの仕事】
- デザインコンポーネントをReactコンポーネントにマッピングする
- コンポーネントの階層構造（親子関係）を設計する
- 各コンポーネントのProps型定義を設計する
- ファイル構成を決定する
- 共通スタイル（Tailwind CSSのカスタム設定）を定義する

【設計原則】
- Atomic Design（atoms → molecules → organisms → templates）を意識する
- 再利用性を最大化し、DRYを徹底する
- TypeScriptのstrict modeに対応した型定義
- Tailwind CSS + shadcn/ui を前提とする
- Server Components / Client Componentsの使い分けを明示する

【出力ルール】
必ず以下のJSON構造のみを返してください。
{
  "project_name": "プロジェクト名",
  "tech_stack": {
    "framework": "Next.js 14+ (App Router)",
    "styling": "Tailwind CSS",
    "ui_library": "shadcn/ui",
    "language": "TypeScript"
  },
  "tailwind_config": {
    "colors": {
      "primary": "#hex",
      "secondary": "#hex",
      "background": "#hex",
      "foreground": "#hex",
      "accent": "#hex"
    },
    "fonts": {
      "heading": "フォント名",
      "body": "フォント名"
    }
  },
  "file_structure": [
    {
      "path": "src/components/ファイル名.tsx",
      "description": "コンポーネントの説明"
    }
  ],
  "components": [
    {
      "name": "ComponentName",
      "file_path": "src/components/ファイル名.tsx",
      "type": "server | client",
      "description": "コンポーネントの概要",
      "props": [
        {
          "name": "propName",
          "type": "TypeScript型",
          "required": true,
          "description": "propの説明"
        }
      ],
      "children": ["子コンポーネント名"],
      "shadcn_components": ["使用するshadcn/uiコンポーネント"]
    }
  ],
  "pages": [
    {
      "path": "src/app/page.tsx",
      "description": "ページの説明",
      "components": ["使用するコンポーネント名"]
    }
  ]
}
"""


class ArchitectAgent:
    """デザイン分析からコンポーネント設計書を作成するアーキテクトエージェント。"""

    name = "Architect"
    description = "デザイン分析をReactコンポーネント設計に変換"

    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    def run(self, design_analysis: dict) -> dict:
        """デザイン分析からコンポーネント設計書を生成する。

        Args:
            design_analysis: DesignerAgent.run()の戻り値

        Returns:
            コンポーネント設計書（Architecture）
        """
        user_message = self._build_prompt(design_analysis)
        return self.claude.generate_json(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=8192,
        )

    @staticmethod
    def _build_prompt(design_analysis: dict) -> str:
        """デザイン分析からプロンプトを構築する。"""
        return f"""\
以下のデザイン分析に基づいて、Reactコンポーネント設計書を作成してください。

【デザイン分析】
{json.dumps(design_analysis, ensure_ascii=False, indent=2)}

上記のカラーパレット・タイポグラフィ・レイアウト・コンポーネント一覧を元に、
Next.js App Router + Tailwind CSS + shadcn/ui での最適な設計書を出力してください。
"""
