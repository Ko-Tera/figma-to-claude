"""Figma REST API クライアント — デザインデータの取得と前処理"""

import os
import re
from urllib.parse import urlparse, parse_qs

import requests


class FigmaClient:
    """Figma REST APIからデザインデータを取得するクライアント。"""

    BASE_URL = "https://api.figma.com/v1"

    def __init__(self, access_token: str | None = None):
        self.token = access_token or os.environ["FIGMA_ACCESS_TOKEN"]
        self._session = requests.Session()
        self._session.headers.update({"X-FIGMA-TOKEN": self.token})

    @staticmethod
    def parse_url(figma_url: str) -> tuple[str, str | None]:
        """FigmaのURLからfile_keyとnode_idを抽出する。

        Returns:
            (file_key, node_id) — node_idはNoneの場合あり
        """
        parsed = urlparse(figma_url)
        path = parsed.path

        # /file/{key}/... or /design/{key}/...
        match = re.search(r"/(?:file|design)/([a-zA-Z0-9]+)", path)
        if not match:
            raise ValueError(f"無効なFigma URL: {figma_url}")

        file_key = match.group(1)

        # node-id from query params
        qs = parse_qs(parsed.query)
        node_id = qs.get("node-id", [None])[0]

        return file_key, node_id

    def get_file(self, file_key: str) -> dict:
        """Figmaファイル全体を取得する。"""
        resp = self._session.get(f"{self.BASE_URL}/files/{file_key}")
        resp.raise_for_status()
        return resp.json()

    def get_node(self, file_key: str, node_id: str) -> dict:
        """特定ノードのデータを取得する。"""
        resp = self._session.get(
            f"{self.BASE_URL}/files/{file_key}/nodes",
            params={"ids": node_id},
        )
        resp.raise_for_status()
        return resp.json()

    def get_images(
        self, file_key: str, node_ids: list[str], fmt: str = "png", scale: int = 2,
    ) -> dict[str, str]:
        """ノードの画像URLを取得する。"""
        resp = self._session.get(
            f"{self.BASE_URL}/images/{file_key}",
            params={
                "ids": ",".join(node_ids),
                "format": fmt,
                "scale": scale,
            },
        )
        resp.raise_for_status()
        return resp.json().get("images", {})

    def fetch_design_data(self, figma_url: str) -> dict:
        """URLからデザインデータを取得し、前処理済みの辞書を返す。"""
        file_key, node_id = self.parse_url(figma_url)

        if node_id:
            raw = self.get_node(file_key, node_id)
            nodes = raw.get("nodes", {})
            # 最初のノードを取得
            node_data = next(iter(nodes.values()), {})
            document = node_data.get("document", {})
        else:
            raw = self.get_file(file_key)
            document = raw.get("document", {})

        # デザイントークンの抽出
        design_data = {
            "file_key": file_key,
            "node_id": node_id,
            "name": raw.get("name", document.get("name", "Untitled")),
            "document": document,
            "colors": self._extract_colors(document),
            "fonts": self._extract_fonts(document),
            "components": self._extract_components(document),
        }
        return design_data

    def _extract_colors(self, node: dict, colors: set | None = None) -> list[str]:
        """ノードツリーからカラーコードを再帰的に抽出する。"""
        if colors is None:
            colors = set()

        for fill in node.get("fills", []):
            color = fill.get("color", {})
            if color:
                r = int(color.get("r", 0) * 255)
                g = int(color.get("g", 0) * 255)
                b = int(color.get("b", 0) * 255)
                a = color.get("a", 1)
                if a < 1:
                    colors.add(f"rgba({r},{g},{b},{a:.2f})")
                else:
                    colors.add(f"#{r:02x}{g:02x}{b:02x}")

        for child in node.get("children", []):
            self._extract_colors(child, colors)

        return sorted(colors)

    def _extract_fonts(self, node: dict, fonts: set | None = None) -> list[dict]:
        """ノードツリーからフォント情報を再帰的に抽出する。"""
        if fonts is None:
            fonts = set()

        style = node.get("style", {})
        font_family = style.get("fontFamily")
        if font_family:
            font_size = style.get("fontSize", 16)
            font_weight = style.get("fontWeight", 400)
            fonts.add((font_family, font_size, font_weight))

        for child in node.get("children", []):
            self._extract_fonts(child, fonts)

        return [
            {"family": f, "size": s, "weight": w}
            for f, s, w in sorted(fonts)
        ]

    def _extract_components(self, node: dict, depth: int = 0) -> list[dict]:
        """ノードツリーからコンポーネント情報を抽出する。"""
        components = []

        node_type = node.get("type", "")
        name = node.get("name", "")

        if node_type in ("FRAME", "COMPONENT", "INSTANCE", "GROUP"):
            bbox = node.get("absoluteBoundingBox", {})
            components.append({
                "name": name,
                "type": node_type,
                "depth": depth,
                "width": bbox.get("width"),
                "height": bbox.get("height"),
                "children_count": len(node.get("children", [])),
            })

        for child in node.get("children", []):
            components.extend(self._extract_components(child, depth + 1))

        return components
