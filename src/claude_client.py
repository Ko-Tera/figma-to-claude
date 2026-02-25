"""Anthropic Claude API 共通クライアント — 全エージェントが使用する共有ラッパー"""

import json
import os
import re
import time

import anthropic


class ClaudeClient:
    """Claude APIの共通クライアント。システムプロンプトとJSON抽出を統一管理する。"""

    _MAX_RETRIES = 3
    _BACKOFF_BASE = 1.0

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"],
        )
        self.model = model

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
    ) -> str:
        """テキスト応答を返す。"""
        for attempt in range(self._MAX_RETRIES):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                return response.content[0].text
            except anthropic.RateLimitError:
                if attempt < self._MAX_RETRIES - 1:
                    wait = self._BACKOFF_BASE * (2 ** attempt)
                    time.sleep(wait)
                    continue
                raise
            except anthropic.APIError:
                if attempt < self._MAX_RETRIES - 1:
                    time.sleep(self._BACKOFF_BASE)
                    continue
                raise

    def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
    ) -> dict:
        """JSON応答を返す。コードフェンスを自動除去してパースする。"""
        raw = self.generate(system_prompt, user_message, max_tokens)
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """テキストからJSON部分を抽出してパースする。"""
        # コードフェンス除去
        cleaned = re.sub(r"```(?:json)?\s*", "", text)
        cleaned = cleaned.strip()

        # 最初の { から最後の } までを抽出
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end + 1]

        return json.loads(cleaned)
