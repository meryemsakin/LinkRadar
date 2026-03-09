"""
Query Parser — Doğal dil sorgusundan filtre çıkarma
Kullanıcı "2025 yılına ait Excel raporlarını listele" dediğinde
year=2025, file_type=xlsx çıkarır.
"""
from __future__ import annotations

import json
import os
import re
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

QUERY_PARSER_PROMPT = """Sen bir sorgu ayrıştırıcısınısın. Kullanıcının doğal dil sorgusundan filtreleme parametreleri çıkarırsın.

Çıkar:
- year: Yıl (örn: "2025", "2024"). Yoksa null.
- month: Ay adı (Türkçe, örn: "Ocak", "Şubat"). Yoksa null.
- category: Kategori veya konu (örn: "petrol", "doğalgaz", "elektrik"). Yoksa null.
- file_type: Dosya türü (xlsx, pdf, docx, csv). Yoksa null.

Kurallar:
- Sadece açıkça belirtilen filtreleri çıkar, tahmin etme.
- "Son raporlar" gibi belirsiz ifadelerde yıl = mevcut yıl olarak ALMA, null bırak.
- "Excel" → file_type: "xlsx", "Word" → file_type: "docx", "PDF" → file_type: "pdf"
- Ayları Türkçe olarak döndür: "Ocak", "Şubat", "Mart", vs.

JSON formatında döndür:
{
  "year": "2025" | null,
  "month": "Ocak" | null,
  "category": "petrol" | null,
  "file_type": "xlsx" | null,
  "understood_intent": "kısa açıklama"
}
"""


async def parse_user_query(query: str) -> dict:
    """
    Doğal dil sorgusunu filtre parametrelerine çevirir.
    Önce regex ile hızlı çıkarma, LLM ile zenginleştirme.
    """
    # ─── Hızlı regex çıkarımı (LLM'siz) ──────────────
    quick_filters = _quick_extract(query)

    # LLM API key yoksa sadece regex sonuçlarını döndür
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.info(f"🔍 Quick extract: {quick_filters}")
        return quick_filters

    # ─── LLM ile zenginleştirme ───────────────────────
    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        response = await llm.ainvoke([
            SystemMessage(content=QUERY_PARSER_PROMPT),
            HumanMessage(content=f"Kullanıcı sorgusu: {query}"),
        ])

        parsed = _parse_json(response.content)

        if parsed:
            filters = {
                "year": parsed.get("year"),
                "month": parsed.get("month"),
                "category": parsed.get("category"),
                "file_type": parsed.get("file_type"),
            }
            # None değerleri temizle
            filters = {k: v for k, v in filters.items() if v}
            intent = parsed.get("understood_intent", "")
            logger.info(f"🧠 LLM parsed: {filters} — intent: {intent}")
            return filters

    except Exception as e:
        logger.warning(f"LLM query parse başarısız: {e}, regex sonuçlarına dönülüyor")

    return quick_filters


def _quick_extract(query: str) -> dict:
    """Regex ile hızlı filtre çıkarımı (LLM gerektirmez)."""
    filters = {}
    query_lower = query.lower()

    # Yıl
    year_match = re.findall(r'\b(20[12]\d)\b', query)
    if year_match:
        filters["year"] = year_match[0]

    # Ay (Türkçe)
    months = {
        "ocak": "Ocak", "şubat": "Şubat", "mart": "Mart", "nisan": "Nisan",
        "mayıs": "Mayıs", "haziran": "Haziran", "temmuz": "Temmuz",
        "ağustos": "Ağustos", "eylül": "Eylül", "ekim": "Ekim",
        "kasım": "Kasım", "aralık": "Aralık",
    }
    for key, val in months.items():
        if key in query_lower:
            filters["month"] = val
            break

    # Dosya türü
    if "excel" in query_lower or "xlsx" in query_lower:
        filters["file_type"] = "xlsx"
    elif "word" in query_lower or "docx" in query_lower:
        filters["file_type"] = "docx"
    elif "pdf" in query_lower:
        filters["file_type"] = "pdf"
    elif "csv" in query_lower:
        filters["file_type"] = "csv"

    return filters


def _parse_json(text: str) -> dict | None:
    """LLM yanıtından JSON parse eder."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        start = 1
        end = -1 if lines[-1].strip() == "```" else len(lines)
        cleaned = "\n".join(lines[start:end])

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}") + 1
        if start_idx >= 0 and end_idx > start_idx:
            try:
                return json.loads(cleaned[start_idx:end_idx])
            except json.JSONDecodeError:
                pass
    return None
