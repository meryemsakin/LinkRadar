from __future__ import annotations
"""
Verifier Agent — Feedback Loop & Quality Gate
Analiz sonuçlarını doğrular, eleştirel göz ile kontrol eder.
Gerekirse File Scout'a geri besleme gönderir.
"""

import logging
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


async def verifier_node(state: AgentState) -> dict:
    """
    Analiz sonuçlarını doğrulayan eleştirel kontrol noktası.

    Kontroller:
    1. Yeterli dosya bulundu mu? (0 dosya → re-crawl tetikle)
    2. Başarı oranı kabul edilebilir mi? (<%50 → uyarı)
    3. Dönem tutarlılığı: filtrelerle eşleşen sonuçlar var mı?
    4. Boş özet var mı? (LLM hatası → retry candidate)

    Feedback loop:
    - Sorun tespit edilirse state'e "needs_retry" ve "retry_reason" yazar
    - Graph router bu state'i okuyup re-crawl veya re-analysis tetikler
    """
    analyzed_files = state.get("analyzed_files", [])
    file_list = state.get("file_list", [])
    user_filters = state.get("user_filters", {})
    raw_links = state.get("raw_links", [])
    retry_count = state.get("retry_count", 0)

    total = len(analyzed_files)
    successful = [f for f in analyzed_files if f.get("status") == "success"]
    failed = [f for f in analyzed_files if f.get("status") == "error"]

    issues = []
    feedback = {}

    # ─── Check 1: Dosya sayısı tutarlılığı ────────
    if total == 0 and len(raw_links) > 10:
        issues.append(
            f"CRITICAL: {len(raw_links)} link bulunmasına rağmen 0 dosya analiz edildi. "
            "File Scout'un link detection stratejisi yetersiz olabilir."
        )
        if retry_count < 1:
            feedback["needs_retry"] = True
            feedback["retry_reason"] = "zero_files_with_links"
            feedback["retry_count"] = retry_count + 1

    # ─── Check 2: Başarı oranı ────────────────────
    if total > 0:
        success_rate = len(successful) / total
        if success_rate < 0.5:
            issues.append(
                f"WARNING: Başarı oranı düşük: {len(successful)}/{total} "
                f"({success_rate:.0%}). Yaygın hata: "
                + _most_common_error(failed)
            )
        elif success_rate < 0.8:
            issues.append(
                f"INFO: {len(failed)}/{total} dosya başarısız "
                f"({1-success_rate:.0%} hata oranı)."
            )

    # ─── Check 3: Boş özetler ────────────────────
    empty_summaries = [
        f for f in successful
        if not f.get("summary") or len(f.get("summary", "")) < 20
    ]
    if empty_summaries:
        issues.append(
            f"WARNING: {len(empty_summaries)} dosyanın özeti boş veya çok kısa. "
            "LLM bağlantı sorunu olabilir."
        )

    # ─── Check 4: Filtre tutarlılığı ──────────────
    if user_filters.get("year"):
        year = user_filters["year"]
        matching = [
            f for f in successful
            if year in str(f.get("period", "")) or year in str(f.get("link_text", ""))
        ]
        if successful and not matching:
            issues.append(
                f"WARNING: Hiçbir başarılı dosya '{year}' yıl filtresine uymuyor. "
                "Dönem tespiti hatalı olabilir."
            )

    # ─── Log results ──────────────────────────────
    if issues:
        for issue in issues:
            logger.warning(f"🔍 Verifier: {issue}")
    else:
        logger.info(f"✅ Verifier: Tüm kontroller geçti ({len(successful)}/{total})")

    return {
        "verification_issues": issues,
        **feedback,
    }


def _most_common_error(failed_files: list) -> str:
    """En yaygın hata türünü belirler."""
    if not failed_files:
        return "bilinmiyor"

    errors = [f.get("error_message", "") for f in failed_files]
    # Basit frequency analizi
    error_types = {}
    for err in errors:
        if "indirme" in err.lower():
            error_types["İndirme hatası"] = error_types.get("İndirme hatası", 0) + 1
        elif "parse" in err.lower() or "okuma" in err.lower():
            error_types["Parse hatası"] = error_types.get("Parse hatası", 0) + 1
        elif "timeout" in err.lower():
            error_types["Timeout"] = error_types.get("Timeout", 0) + 1
        else:
            error_types["Diğer"] = error_types.get("Diğer", 0) + 1

    if error_types:
        most_common = max(error_types, key=error_types.get)
        return f"{most_common} ({error_types[most_common]} dosya)"
    return "bilinmiyor"
