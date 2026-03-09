from __future__ import annotations
"""
Crawl Tool — Multi-Strategy Web Crawler
Strateji 1: Crawl4AI (JS rendering, Playwright)
Strateji 2: httpx + BeautifulSoup (fallback — JS gerektirmeyen sayfalar)
Strateji 3: Requests + regex (desperation fallback)
"""

import re
import logging
from typing import Any
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


async def _crawl_with_crawl4ai(url: str, scroll: bool = True) -> dict:
    """Strateji 1: Crawl4AI ile JS rendering destekli crawl."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
        )

        run_config = CrawlerRunConfig(
            wait_until="networkidle",
            page_timeout=30000,
            scan_full_page=scroll,
            scroll_delay=0.5,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

            if not result.success:
                return {"success": False, "error": f"Crawl4AI başarısız: {result.error_message}"}

            links = []
            if result.links:
                for category in ["external", "internal"]:
                    for link in result.links.get(category, []):
                        links.append({
                            "href": link.get("href", ""),
                            "text": link.get("text", ""),
                            "title": link.get("title", ""),
                        })

            return {
                "success": True,
                "markdown": result.markdown or "",
                "links": links,
                "strategy": "crawl4ai",
            }

    except Exception as e:
        logger.warning(f"Crawl4AI hatası: {type(e).__name__}: {str(e)}")
        return {"success": False, "error": f"Crawl4AI hatası: {str(e)}"}


async def _crawl_with_httpx(url: str) -> dict:
    """Strateji 2: httpx + BeautifulSoup — JS gerektirmeyen sayfalar için."""
    try:
        import httpx
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        }

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            verify=False,
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "html.parser")

        # Text extraction
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        # Link extraction
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            link_text = a_tag.get_text(strip=True)
            title = a_tag.get("title", "")

            # İçindeki img'nin src'sinden dosya türü ipucu
            img = a_tag.find("img")
            if img and img.get("src"):
                img_src = img["src"].lower()
                if not title and not link_text:
                    # img src'den tür ipucu
                    if "word" in img_src:
                        link_text = "[Word]"
                    elif "excel" in img_src:
                        link_text = "[Excel]"
                    elif "pdf" in img_src:
                        link_text = "[PDF]"
                # title'ı img alt'tan al
                if not title and img.get("alt"):
                    title = img["alt"]

            links.append({
                "href": href,
                "text": link_text,
                "title": title,
            })

        return {
            "success": True,
            "markdown": text[:50000],  # Max 50k char
            "links": links,
            "strategy": "httpx+bs4",
        }

    except Exception as e:
        logger.warning(f"httpx fallback hatası: {type(e).__name__}: {str(e)}")
        return {"success": False, "error": f"httpx hatası: {str(e)}"}


@tool
async def crawl_page(
    url: str,
    scroll_to_bottom: bool = True,
) -> dict[str, Any]:
    """
    Multi-strategy web page crawler.
    Önce Crawl4AI (JS rendering), başarısız olursa httpx + BeautifulSoup.

    Args:
        url: Crawl edilecek sayfa URL'si
        scroll_to_bottom: Sayfanın sonuna kadar scroll yap (Crawl4AI)

    Returns:
        success, markdown, links, strategy
    """
    if not url or not url.startswith("http"):
        return {"success": False, "error": "Geçersiz URL", "links": [], "markdown": ""}

    logger.info(f"🌐 Crawl başlıyor: {url}")

    # Strateji 1: Crawl4AI
    result = await _crawl_with_crawl4ai(url, scroll_to_bottom)
    if result["success"]:
        logger.info(f"✅ Crawl4AI başarılı: {len(result['links'])} link bulundu")
        return result

    logger.warning(f"⚠️ Crawl4AI başarısız, httpx fallback deneniyor...")

    # Strateji 2: httpx + BeautifulSoup
    result = await _crawl_with_httpx(url)
    if result["success"]:
        logger.info(
            f"✅ httpx fallback başarılı: {len(result['links'])} link bulundu"
        )
        return result

    # Her iki strateji de başarısız
    return {
        "success": False,
        "error": (
            "Sayfa hiçbir yöntemle crawl edilemedi. "
            "1) Crawl4AI (JS rendering) başarısız "
            "2) httpx+BeautifulSoup (static) başarısız. "
            "Site muhtemelen güçlü bot koruması kullanıyor."
        ),
        "links": [],
        "markdown": "",
    }
