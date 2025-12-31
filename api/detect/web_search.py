"""Web search module for retrieving context from the internet."""

from typing import List, Dict, Any, Optional
from ddgs import DDGS
from crawl4ai import AsyncWebCrawler, BrowserConfig
import logging
import asyncio
import aiohttp
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_chromium_executable() -> Optional[str]:
    """
    Find chromium executable in Playwright browsers directory.

    Returns:
        Path to chromium executable or None if not found
    """
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/app/.cache/ms-playwright")
    browsers_dir = Path(browsers_path)

    if not browsers_dir.exists():
        logger.warning(f"Playwright browsers directory not found: {browsers_dir}")
        return None

    # Ищем директорию chromium-*
    chromium_dirs = list(browsers_dir.glob("chromium-*"))
    if not chromium_dirs:
        logger.warning(f"No chromium directories found in {browsers_dir}")
        return None

    chromium_dir = chromium_dirs[0]

    # Ищем исполняемый файл chrome в разных возможных местах
    possible_paths = [
        chromium_dir / "chrome-linux64" / "chrome",
        chromium_dir / "chrome-linux" / "chrome",
        chromium_dir / "chrome" / "chrome",
    ]

    for path in possible_paths:
        if path.exists() and path.is_file():
            logger.info(f"Found chromium executable: {path}")
            return str(path.absolute())

    # Если не нашли в стандартных местах, ищем рекурсивно
    chrome_files = list(chromium_dir.rglob("chrome"))
    if chrome_files:
        chrome_path = chrome_files[0]
        if chrome_path.is_file():
            logger.info(f"Found chromium executable (recursive search): {chrome_path}")
            return str(chrome_path.absolute())

    logger.warning(f"Chromium executable not found in {chromium_dir}")
    return None


class WebSearchService:
    """Service for performing web searches and extracting content."""

    def __init__(self):
        """Initialize the web search service."""
        # Настраиваем путь к браузерам Playwright
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/app/.cache/ms-playwright")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

        # Находим путь к chromium executable
        chromium_path = _find_chromium_executable()

        # Создаем конфигурацию браузера
        browser_config = None
        if chromium_path:
            browser_config = BrowserConfig(
                browser_type="chromium",
                playwright_browser_path=chromium_path,
                headless=True,
                verbose=False,
            )
            logger.info(f"Using chromium browser at: {chromium_path}")
        else:
            logger.warning(
                "Chromium executable not found, using default Playwright configuration. "
                "This may fail if browsers are not installed."
            )
            browser_config = BrowserConfig(
                browser_type="chromium",
                headless=True,
                verbose=False,
            )

        self.crawler = AsyncWebCrawler(config=browser_config)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session for URL validation."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5), connector=aiohttp.TCPConnector(limit=10)
            )
        return self._session

    async def _is_url_accessible(self, url: str) -> bool:
        """
        Check if URL is accessible (not dead).

        Args:
            url: URL to check

        Returns:
            True if URL is accessible, False otherwise
        """
        try:
            session = await self._get_session()
            async with session.head(url, allow_redirects=True) as response:
                # Проверяем, что статус код успешный (2xx или 3xx)
                return 200 <= response.status < 400
        except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
            logger.debug(f"URL {url} is not accessible: {str(e)}")
            return False

    async def search_and_extract(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the web and extract content from results.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of dictionaries containing search results with extracted content
        """
        try:
            # Perform DuckDuckGo search to get URLs
            # Запрашиваем больше результатов, чтобы после фильтрации мертвых ссылок осталось достаточно
            ddgs_results = DDGS().text(query, max_results=max_results * 3)

            results = []

            # Extract content from each URL using crawl4ai
            for result in ddgs_results:
                try:
                    url = result.get("href") or result.get("link")
                    if not url:
                        continue

                    # Проверяем доступность URL перед обработкой
                    if not await self._is_url_accessible(url):
                        logger.debug(f"Skipping dead link: {url}")
                        continue

                    # Crawl the webpage
                    try:
                        crawl_result = await self.crawler.arun(url=url, bypass_cache=True, verbose=False)
                    except Exception as crawl_error:
                        # Если Playwright не установлен или другая ошибка при краулинге
                        logger.warning(f"Failed to crawl {url}: {str(crawl_error)}")
                        # Используем описание из поиска как fallback
                        results.append(
                            {
                                "title": result.get("title", ""),
                                "url": url,
                                "content": result.get("body", ""),
                                "description": result.get("body", "")[:500],
                            }
                        )
                        if len(results) >= max_results:
                            break
                        continue

                    if crawl_result and crawl_result.success:
                        # Extract main content from the crawled page
                        extracted_content = crawl_result.extracted_content

                        results.append(
                            {
                                "title": result.get("title", ""),
                                "url": url,
                                "content": extracted_content,
                                "description": result.get("body", "")[:500],  # First 500 chars as description
                            }
                        )

                        if len(results) >= max_results:
                            break
                    else:
                        # Если crawl не удался, но URL доступен, используем описание из поиска
                        # Но только если URL действительно доступен (уже проверили выше)
                        results.append(
                            {
                                "title": result.get("title", ""),
                                "url": url,
                                "content": result.get("body", ""),
                                "description": result.get("body", "")[:500],
                            }
                        )

                        if len(results) >= max_results:
                            break

                except Exception as e:
                    logger.warning(f"Failed to process {url}: {str(e)}")
                    # Не добавляем результат, если произошла ошибка
                    continue

            return results

        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            return []

    async def get_symbiosis_context(self, query: str = "symbiosis ecological relationships") -> str:
        """
        Get context specifically about symbiosis for the chatbot.

        Args:
            query: Search query (default is about symbiosis)

        Returns:
            Formatted context string about symbiosis
        """
        results = await self.search_and_extract(query, max_results=3)

        if not results:
            return ""

        context_parts = []
        context_parts.append("### Из веб-поиска:")

        for i, result in enumerate(results, 1):
            title = result.get("title", "Без названия")
            content = result.get("content", "")[:1000]  # First 1000 chars
            url = result.get("url", "")

            # Компактный формат: название как ссылка, затем содержание
            context_parts.append(f"[{title}]({url})")
            context_parts.append(f"{content}")
            context_parts.append("")

        return "\n".join(context_parts)

    async def close(self):
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()


# Global instance
web_search_service = WebSearchService()
