from __future__ import annotations
"""
Web Analyst Agent
Sayfa analiz ve yapı keşif node'ları.
page_analyzer_node: Sayfayı crawl eder ve yapısını analiz eder.
structure_mapper_node: Hiyerarşiyi ve filtreleme boyutlarını belirler.
filter_confirm_node: HITL noktası — kullanıcıdan filtre onayı alır.
"""

import json
import logging
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.graph.state import AgentState
from src.prompts.web_analyst import WEB_ANALYST_SYSTEM_PROMPT
from src.tools.crawl_tool import crawl_page

logger = logging.getLogger(__name__)


def _get_llm():
    """LLM instance oluşturur."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )


def _parse_json_response(text: str) -> dict:
    """LLM yanıtından JSON parse eder (markdown code block temizliği dahil)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # İlk ve son ``` satırlarını kaldır
        start = 1 if lines[0].startswith("```") else 0
        end = -1 if lines[-1].strip() == "```" else len(lines)
        cleaned = "\n".join(lines[start:end])
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Basit fallback: süslü parantezler arasını al
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}") + 1
        if start_idx >= 0 and end_idx > start_idx:
            try:
                return json.loads(cleaned[start_idx:end_idx])
            except json.JSONDecodeError:
                pass
        return {}


async def page_analyzer_node(state: AgentState) -> dict:
    """
    Sayfayı crawl eder ve yapısını analiz eder.
    Başarısız olursa error state'i set eder.

    Bu node'un görevi:
    1. crawl_page tool ile sayfayı çek
    2. LLM ile yapı analizi yap
    3. Sonuçları state'e yaz
    """
    url = state["url"]
    logger.info(f"📄 Sayfa analiz ediliyor: {url}")

    try:
        # Crawl4AI ile sayfayı çek
        crawl_result = await crawl_page.ainvoke({
            "url": url,
            "scroll_to_bottom": True,
        })

        if not crawl_result["success"]:
            logger.error(f"Crawl başarısız: {crawl_result['error']}")
            return {
                "error": crawl_result["error"],
                "phase": "failed",
            }

        markdown = crawl_result["markdown"]
        links = crawl_result["links"]

        if not markdown and not links:
            return {
                "error": "Sayfa içeriği boş. JavaScript rendering sorunu olabilir.",
                "phase": "failed",
            }

        # LLM ile yapı analizi
        llm = _get_llm()
        # Token optimizasyonu: markdown'ı 8000 char ile sınırla
        truncated_markdown = markdown[:8000] if markdown else ""
        # Linkleri 100 ile sınırla
        truncated_links = links[:100]

        structure_response = await llm.ainvoke([
            SystemMessage(content=WEB_ANALYST_SYSTEM_PROMPT),
            HumanMessage(content=f"""
Sayfa URL: {url}

Sayfa İçeriği (Markdown):
{truncated_markdown}

Sayfadaki Linkler (ilk 100):
{json.dumps(truncated_links, ensure_ascii=False, indent=2)}
"""),
        ])

        # Structured output parse
        parsed = _parse_json_response(structure_response.content)

        if not parsed:
            logger.warning("LLM yanıtı parse edilemedi, varsayılan değerler kullanılıyor")
            parsed = {
                "institution": "unknown",
                "sector": "unknown",
                "content_type": "unknown",
                "organization_scheme": "unknown",
                "available_dimensions": [],
                "language": "tr",
                "confidence": 0.3,
            }

        logger.info(
            f"✅ Sayfa analiz edildi: {parsed.get('institution', 'unknown')} — "
            f"Güven: {parsed.get('confidence', 0)}"
        )

        return {
            "page_markdown": markdown,
            "raw_links": links,
            "page_meta": parsed,
            "phase": "analyzed",
        }

    except Exception as e:
        logger.error(f"page_analyzer_node hatası: {type(e).__name__}: {str(e)}")
        return {
            "error": f"Sayfa analiz hatası: {type(e).__name__}: {str(e)}",
            "phase": "failed",
        }


async def structure_mapper_node(state: AgentState) -> dict:
    """
    Sayfa yapısını derinlemesine analiz eder.
    page_meta'dan gelen bilgileri link pattern'leri ile zenginleştirir.
    """
    page_meta = state.get("page_meta", {})
    raw_links = state.get("raw_links", [])

    logger.info("🗺️  Yapı haritalanıyor...")

    # Link pattern analizi (deterministic — LLM yok)
    file_extensions = {}
    year_patterns = set()
    category_hints = set()

    for link in raw_links:
        href = link.get("href", "")
        text = link.get("text", "")

        # Uzantı sayımı
        for ext in [".xlsx", ".xls", ".csv", ".docx", ".doc", ".pdf", ".zip"]:
            if ext in href.lower():
                file_extensions[ext] = file_extensions.get(ext, 0) + 1

        # Yıl pattern'i
        import re
        years = re.findall(r"20[12]\d", href + " " + text)
        year_patterns.update(years)

    # Mevcut dimensions'ı zenginleştir
    available_dimensions = page_meta.get("available_dimensions", [])

    # Keşfedilen yılları ekle (eğer yoksa)
    if year_patterns:
        has_year_dim = any(d.get("name", "").lower() in ["yıl", "year"] for d in available_dimensions)
        if not has_year_dim:
            available_dimensions.append({
                "name": "Yıl",
                "type": "temporal",
                "values": sorted(list(year_patterns)),
                "is_hierarchical": True,
            })

    updated_meta = {**page_meta, "available_dimensions": available_dimensions}

    logger.info(
        f"✅ Yapı haritalandı: {len(file_extensions)} dosya türü, "
        f"{len(year_patterns)} yıl pattern'i"
    )

    return {
        "page_meta": updated_meta,
    }


async def filter_confirm_node(state: AgentState) -> dict:
    """
    Human-in-the-loop noktası: kullanıcıya keşfedilen boyutları gösterir.
    Interactive modda çalışırken interrupt kullanılır.
    Non-interactive modda otomatik devam eder.
    """
    # Non-interactive modda otomatik devam
    return {}
