"""
Content Analyst Agent — v2 (Agentic Architecture)
Paralel dosya işleme, adaptive parsing, smart error recovery.
"""
from __future__ import annotations

import asyncio
import json
import os
import logging
import time
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Optional, Dict, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential

from src.graph.state import AgentState, FileAnalysisState
from src.prompts.content_analyst import CONTENT_ANALYST_SYSTEM_PROMPT
from src.tools.download_tool import download_file
from src.tools.parsers import parse_file

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "5"))
LLM_CONCURRENCY = 3  # Rate limiting koruması

# Semaphore'ları event loop başına lazily oluştur
# (Streamlit/asyncio.run() farklı loop kullandığında hata vermemesi için)
_semaphores: Dict[int, Tuple[asyncio.Semaphore, asyncio.Semaphore]] = {}


def _get_semaphores() -> Tuple[asyncio.Semaphore, asyncio.Semaphore]:
    """Mevcut event loop için semaphore çifti döndürür."""
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    if loop_id not in _semaphores:
        _semaphores[loop_id] = (
            asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS),
            asyncio.Semaphore(LLM_CONCURRENCY),
        )
    return _semaphores[loop_id]


def _get_llm():
    """LLM instance oluşturur."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def _call_llm_with_retry(llm, messages):
    """LLM çağrısını retry ile yapar (rate limiting koruması)."""
    _, llm_sem = _get_semaphores()
    async with llm_sem:
        return await llm.ainvoke(messages)


async def generate_summary(parsed_metadata: dict, file_info: dict) -> str:
    """Parse edilmiş metadata'dan LLM ile dosya özeti üretir."""
    llm = _get_llm()

    metadata_str = json.dumps(parsed_metadata, ensure_ascii=False, indent=2, default=str)

    # Adaptive token budget: büyük dosyalar için daha fazla context
    max_chars = 3000 if parsed_metadata.get("total_pages", 0) > 10 else 1500
    if len(metadata_str) > max_chars:
        metadata_str = metadata_str[:max_chars] + "\n... (truncated)"

    try:
        response = await _call_llm_with_retry(llm, [
            SystemMessage(content=CONTENT_ANALYST_SYSTEM_PROMPT),
            HumanMessage(content=f"""
Dosya Adı: {file_info.get('filename', 'unknown')}
Dosya Türü: {file_info.get('file_type', 'unknown')}
Uzantı: {file_info.get('extension', 'unknown')}
Link Metni: {file_info.get('link_text', '')}
Dönem: {file_info.get('period', 'unknown')}

Çıkarılan Metadata:
{metadata_str}
"""),
        ])
        return response.content.strip()
    except Exception as e:
        logger.warning(f"LLM özet üretimi başarısız: {str(e)}")
        return f"Dosya metadata'sı çıkarıldı ancak özet üretilemedi: {file_info.get('filename', 'unknown')}"


# ─── Content-Type Handling ────────────────────────────────
CONTENT_TYPE_MAP = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/pdf": ".pdf",
    "text/csv": ".csv",
    "application/zip": ".zip",
}


def _content_type_to_ext(content_type: str) -> str:
    """HTTP Content-Type header'dan dosya uzantısı çıkarır."""
    if not content_type:
        return ""
    ct = content_type.split(";")[0].strip().lower()

    if ct in CONTENT_TYPE_MAP:
        return CONTENT_TYPE_MAP[ct]

    # Partial match (EPDK gibi sitelerde .main+xml suffix olabiliyor)
    if "spreadsheetml" in ct or "excel" in ct:
        return ".xlsx"
    if "wordprocessingml" in ct or "msword" in ct:
        return ".docx"
    if "pdf" in ct:
        return ".pdf"

    return ""


def _detect_ext_from_error(error_msg: str) -> Optional[str]:
    """Parser hata mesajından gerçek dosya türünü çıkarır."""
    error_lower = error_msg.lower()
    if "spreadsheetml" in error_lower or "excel" in error_lower:
        return ".xlsx"
    elif "wordprocessingml" in error_lower:
        return ".docx"
    elif "pdf" in error_lower:
        return ".pdf"
    return None


# ─── Single File Analyzer ────────────────────────────────
async def _analyze_single_file(file_info: dict, retry_count: int = 0) -> dict:
    """
    Tek bir dosyayı analiz eder — semaphore ile concurrency kontrollü.
    Pipeline: indir → parse (adaptive fallback) → özetle

    Retry stratejisi:
    - İndirme hatası: farklı timeout ile tekrar dene
    - Parse hatası: content-type veya error detection ile doğru format'ı bul
    - LLM hatası: exponential backoff ile retry
    """
    filename = file_info.get("filename", "unknown")
    extension = file_info.get("extension", "")

    logger.info(f"📥 [{retry_count}] Dosya analiz ediliyor: {filename}")

    try:
        # 1. İndir — semaphore ile concurrent ama kontrollü
        dl_sem, _ = _get_semaphores()
        async with dl_sem:
            download_result = await download_file.ainvoke({
                "url": file_info["url"],
                "timeout": 30 + (retry_count * 15),  # Retry'da timeout artır
                "max_size_mb": 50.0,
            })

        if not download_result["success"]:
            error = download_result["error"]

            # Smart retry: timeout ise daha uzun süre ile tekrar dene
            if retry_count < 2 and ("timeout" in error.lower() or "zaman" in error.lower()):
                logger.info(f"🔄 Timeout retry: {filename} (attempt {retry_count + 1})")
                return await _analyze_single_file(file_info, retry_count + 1)

            return {
                **file_info,
                "summary": "",
                "metadata": {},
                "status": "error",
                "error_message": f"İndirme hatası: {error}",
                "size_bytes": 0,
            }

        content = download_result["content"]
        size_bytes = download_result["size_bytes"]
        content_type = download_result.get("content_type", "")

        # Extension yoksa content-type'dan çıkar
        if not extension:
            extension = _content_type_to_ext(content_type)
            if extension:
                logger.info(f"📎 Content-type'dan uzantı: {extension}")

        # 2. Parse — multi-fallback chain
        parsed = await parse_file(content, extension, filename)

        # Fallback 1: Content-type ile farklı uzantı dene
        if not parsed.get("success", False) and content_type:
            ct_ext = _content_type_to_ext(content_type)
            if ct_ext and ct_ext != extension:
                logger.info(f"🔄 Fallback (content-type): {ct_ext}")
                parsed = await parse_file(content, ct_ext, filename)
                if parsed.get("success", False):
                    extension = ct_ext

        # Fallback 2: Hata mesajından dosya türünü çıkar
        if not parsed.get("success", False):
            fallback_ext = _detect_ext_from_error(parsed.get("error", ""))
            if fallback_ext and fallback_ext != extension:
                logger.info(f"🔄 Fallback (error-detect): {extension} → {fallback_ext}")
                parsed = await parse_file(content, fallback_ext, filename)
                if parsed.get("success", False):
                    extension = fallback_ext

        # Fallback 3: Tüm desteklenen formatları dene (brute-force)
        if not parsed.get("success", False):
            for try_ext in [".xlsx", ".docx", ".pdf", ".csv"]:
                if try_ext != extension:
                    parsed = await parse_file(content, try_ext, filename)
                    if parsed.get("success", False):
                        extension = try_ext
                        logger.info(f"🔄 Brute-force fallback başarılı: {try_ext}")
                        break

        if not parsed.get("success", False):
            logger.warning(f"⚠️ Tüm parse denemeleri başarısız: {filename}")
            return {
                **file_info,
                "summary": f"Dosya indirildi ({size_bytes} bytes) ancak içerik hiçbir parser ile okunamadı.",
                "metadata": {},
                "status": "error",
                "error_message": f"Tüm formatlar denendi, okuma başarısız: {parsed.get('error', 'unknown')}",
                "size_bytes": size_bytes,
            }

        # 3. LLM ile özet üret
        summary = await generate_summary(parsed, file_info)

        logger.info(f"✅ Dosya analiz edildi: {filename}")

        return {
            **file_info,
            "summary": summary,
            "metadata": {k: v for k, v in parsed.items() if k != "success" and k != "error"},
            "status": "success",
            "error_message": None,
            "size_bytes": size_bytes,
        }

    except Exception as e:
        logger.error(f"❌ Dosya analiz hatası: {filename} — {type(e).__name__}: {str(e)}")
        return {
            **file_info,
            "summary": "",
            "metadata": {},
            "status": "error",
            "error_message": f"Beklenmeyen hata: {type(e).__name__}: {str(e)}",
            "size_bytes": 0,
        }


# ─── Main Node — Parallel Execution ──────────────────────
async def content_analyzer_node(state: AgentState) -> dict:
    """
    file_list'teki tüm dosyaları PARALEL olarak analiz eder.
    asyncio.gather ile concurrent execution, semaphore ile rate limiting.

    Concurrency model:
    - Download: MAX_CONCURRENT_DOWNLOADS (default 5) eşzamanlı indirme
    - LLM: LLM_CONCURRENCY (default 3) eşzamanlı API çağrısı
    - Her dosya bağımsız hata izolasyonuna sahip
    """
    file_list = state.get("file_list", [])
    total = len(file_list)
    logger.info(f"📦 {total} dosya PARALEL analiz edilecek (max {MAX_CONCURRENT_DOWNLOADS} concurrent)")

    start_time = time.time()

    # Tüm dosyaları paralel başlat — asyncio.gather ile
    tasks = [_analyze_single_file(file_info) for file_info in file_list]
    analyzed_files = await asyncio.gather(*tasks, return_exceptions=True)

    # Exception'ları handle et
    results = []
    for i, result in enumerate(analyzed_files):
        if isinstance(result, Exception):
            logger.error(f"❌ Paralel task exception: {type(result).__name__}: {result}")
            results.append({
                **file_list[i],
                "summary": "",
                "metadata": {},
                "status": "error",
                "error_message": f"Paralel işleme hatası: {type(result).__name__}",
                "size_bytes": 0,
            })
        else:
            results.append(result)

    elapsed = time.time() - start_time
    successful = sum(1 for f in results if f.get("status") == "success")
    logger.info(
        f"📊 Analiz tamamlandı: {successful}/{total} başarılı "
        f"({elapsed:.1f}s, {elapsed/max(total,1):.1f}s/dosya ortalama)"
    )

    return {
        "analyzed_files": results,
        "phase": "processing",
    }


# ─── Smart Error Handler ─────────────────────────────────
async def error_handler_node(state: AgentState) -> dict:
    """
    Akıllı hata yönetimi — hatayı teşhis eder ve alternatif strateji önerir.
    Sadece mesaj göstermek yerine, kurtarılabilir hataları kurtarmaya çalışır.
    """
    error = state.get("error", "Bilinmeyen hata")
    phase = state.get("phase", "unknown")
    url = state.get("url", "")
    raw_links = state.get("raw_links", [])
    file_list = state.get("file_list", [])

    logger.error(f"🚨 Hata yakalandı (phase: {phase}): {error}")

    # ─── Diagnostic: hatanın nedenini anlayalım ─────────
    diagnosis = []

    if "timeout" in error.lower() or "zaman aşımı" in error.lower():
        diagnosis.append("TIMEOUT")
        user_message = (
            "Sayfa yavaş yanıt veriyor. Olası nedenler: "
            "1) Sunucu yoğun 2) Sayfa çok ağır (JS rendering). "
            "Daha kısa bir timeout ile veya farklı bir saat diliminde tekrar deneyin."
        )
    elif "403" in error or "forbidden" in error.lower():
        diagnosis.append("ACCESS_DENIED")
        user_message = (
            "Sayfaya erişim engellenmiş. Olası nedenler: "
            "1) Bot koruması aktif 2) IP bazlı kısıtlama. "
            "VPN kullanarak veya farklı bir ağdan deneyin."
        )
    elif "404" in error:
        diagnosis.append("NOT_FOUND")
        user_message = "Sayfa bulunamadı. URL'yi kontrol edin — sayfa taşınmış veya kaldırılmış olabilir."
    elif "bulunamadı" in error.lower() or "dosya yok" in error.lower():
        diagnosis.append("NO_FILES_FOUND")

        # Kurtarma denemesi: linkler var ama extension filtresi sert
        if raw_links and not file_list:
            total_links = len(raw_links)
            download_pattern_links = sum(
                1 for l in raw_links
                if "download" in l.get("href", "").lower()
            )
            user_message = (
                f"{error}\n\n"
                f"📊 Teşhis: Sayfada toplam {total_links} link var"
                + (f", bunlardan {download_pattern_links} tanesi download pattern'i içeriyor." if download_pattern_links else ".")
                + "\nFiltre kriterlerini genişletmeyi veya dosya türü filtresini kaldırmayı deneyin."
            )
        else:
            user_message = error
    elif "ssl" in error.lower() or "certificate" in error.lower():
        diagnosis.append("SSL_ERROR")
        user_message = (
            "SSL sertifika hatası. Sitenin sertifikası geçersiz veya süresi dolmuş olabilir."
        )
    else:
        diagnosis.append("UNKNOWN")
        user_message = f"İşlem sırasında bir hata oluştu: {error}"

    logger.info(f"🏥 Teşhis: {', '.join(diagnosis)}")

    return {
        "error": user_message,
        "phase": "failed",
    }
