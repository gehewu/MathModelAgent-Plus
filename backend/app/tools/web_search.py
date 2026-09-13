"""Tavily Web Search 工具，供 Agent 联网搜索真实数据。

配置：.env.dev 中设置 TAVILY_API_KEY 并开启 SEARCH_ENABLED=true 后生效；
未配置时自动降级（enabled 为 False），Agent 不会收到该工具，不影响主流程。
"""

import time
from typing import Any

import httpx

from app.config.setting import settings
from app.utils.log_util import logger

_TAVILY_URL = "https://api.tavily.com/search"
_MAX_RESULTS = 5


class WebSearchTool:
    """基于 Tavily API 的联网搜索工具，带简单内存缓存（按 SEARCH_CACHE_TTL 过期）。"""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    @property
    def enabled(self) -> bool:
        """是否启用：需同时开启 SEARCH_ENABLED 且配置了 TAVILY_API_KEY。"""
        return bool(settings.SEARCH_ENABLED and settings.TAVILY_API_KEY)

    async def search(self, query: str, max_results: int = _MAX_RESULTS) -> list[dict[str, Any]]:
        """搜索并返回结果列表（每条含 title/url/content）。

        Args:
            query: 搜索关键词。
            max_results: 最大返回条数。

        Returns:
            搜索结果列表。

        Raises:
            RuntimeError: Web Search 未启用时抛出。
        """
        if not self.enabled:
            raise RuntimeError(
                "Web Search 未启用：请在 .env.dev 配置 TAVILY_API_KEY 并设置 SEARCH_ENABLED=true"
            )

        now = time.time()
        cached = self._cache.get(query)
        if cached and (now - cached[0]) < settings.SEARCH_CACHE_TTL:
            logger.debug(f"Web Search 命中缓存: {query}")
            return cached[1]

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    _TAVILY_URL,
                    json={
                        "api_key": settings.TAVILY_API_KEY,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error(f"Web Search 调用失败: {e}")
            raise RuntimeError(f"Web Search 调用失败: {e}") from e

        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
            for item in data.get("results", [])
        ]
        self._cache[query] = (now, results)
        logger.info(f"Web Search 完成: {query} -> {len(results)} 条结果")
        return results

    @staticmethod
    def format_results(results: list[dict[str, Any]]) -> str:
        """将搜索结果格式化为可供 LLM 阅读的文本。"""
        if not results:
            return "未搜索到相关结果"
        parts = []
        for i, item in enumerate(results, 1):
            parts.append(
                f"[{i}] 标题: {item.get('title', '')}\n"
                f"    链接: {item.get('url', '')}\n"
                f"    内容: {item.get('content', '')}"
            )
        return "\n".join(parts)
