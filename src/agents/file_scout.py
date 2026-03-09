"""
File Scout Agent
Deterministik dosya keşfi ve filtreleme node'u.
Mümkün olduğunca LLM kullanmadan çalışır.
"""
from __future__ import annotations

import re
import logging
from urllib.parse import urljoin, urlparse, unquote
from src.graph.state import AgentState

logger = logging.getLogger(__name__)

# Desteklenen dosya uzantıları
SUPPORTED_EXTENSIONS = {
    ".xlsx", ".xls", ".csv",     # Spreadsheet
    ".docx", ".doc",              # Word
    ".pdf",                       # PDF
    ".zip", ".rar",               # Archive
    ".txt", ".json", ".xml",      # Diğer
}

# Dosya türü sınıflandırma haritası
FILE_TYPE_MAP = {
    ".xlsx": "spreadsheet",
    ".xls": "spreadsheet",
    ".csv": "spreadsheet",
    ".docx": "document",
    ".doc": "document",
    ".pdf": "pdf",
    ".zip": "archive",
    ".rar": "archive",
    ".txt": "text",
    ".json": "data",
    ".xml": "data",
}

# Türkçe ay isimleri normalizasyon
TURKISH_MONTHS = {
    "ocak": "01", "şubat": "02", "mart": "03", "nisan": "04",
    "mayıs": "05", "haziran": "06", "temmuz": "07", "ağustos": "08",
    "eylül": "09", "ekim": "10", "kasım": "11", "aralık": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def resolve_url(base_url: str, href: str) -> str:
    """Relative URL'yi absolute URL'ye çevirir."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}:{href}"
    return urljoin(base_url, href)


def get_extension(url: str) -> str:
    """URL'den dosya uzantısını çıkarır."""
    # Query string ve fragment'ı temizle
    path = urlparse(url).path
    path = unquote(path)  # URL encode çöz
    # Son noktalı kısımdan uzantıyı al
    if "." in path.split("/")[-1]:
        ext = "." + path.split("/")[-1].rsplit(".", 1)[-1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            return ext
    return ""


def extract_filename(url: str) -> str:
    """URL'den dosya adını çıkarır."""
    path = urlparse(url).path
    path = unquote(path)
    if "/" in path:
        return path.split("/")[-1]
    return path


def classify_file_type(ext: str) -> str:
    """Uzantıdan dosya türü sınıflandırması."""
    return FILE_TYPE_MAP.get(ext.lower(), "other")


def detect_period(text: str, url: str) -> str | None:
    """Link text ve URL'den dönem bilgisi çıkarır."""
    combined = f"{text} {url}".lower()

    # Yıl tespiti
    year_match = re.findall(r"(20[12]\d)", combined)
    year = year_match[0] if year_match else None

    # Ay tespiti
    month = None
    for tr_month, num in TURKISH_MONTHS.items():
        if tr_month in combined:
            month = num
            break

    if not month:
        # Sayısal ay tespiti: _01_, -01-, /01/ gibi
        month_match = re.findall(r"[_\-/](0[1-9]|1[0-2])[_\-/.]", combined)
        if month_match:
            month = month_match[0]

    if year and month:
        return f"{year}-{month}"
    elif year:
        return year
    return None


def apply_filters(
    files: list[dict],
    user_filters: dict,
    page_meta: dict | None = None,
) -> list[dict]:
    """
    Kullanıcı filtrelerini uygular.
    Deterministik filtreleme: LLM kullanmaz.
    """
    filtered = files
    reasons = []

    # Yıl filtresi
    year = user_filters.get("year")
    if year:
        before = len(filtered)
        filtered = [
            f for f in filtered
            if year in f.get("url", "") or year in f.get("link_text", "") or
            (f.get("period") and year in str(f.get("period", "")))
        ]
        excluded = before - len(filtered)
        if excluded > 0:
            reasons.append(f"{excluded} dosya yıl filtresi ({year}) ile hariç tutuldu")

    # Ay filtresi
    month = user_filters.get("month")
    if month:
        month_lower = month.lower()
        month_num = TURKISH_MONTHS.get(month_lower, month)
        before = len(filtered)
        filtered = [
            f for f in filtered
            if month_lower in f.get("link_text", "").lower() or
            month_lower in f.get("url", "").lower() or
            month_num in f.get("url", "") or
            (f.get("period") and month_num in str(f.get("period", "")))
        ]
        excluded = before - len(filtered)
        if excluded > 0:
            reasons.append(f"{excluded} dosya ay filtresi ({month}) ile hariç tutuldu")

    # Kategori filtresi (daha akıllı eşleşme, URL içindeki path'leri de tarar)
    category = user_filters.get("category")
    if category:
        cat_lower = category.lower()
        # Kategori "enflasyon" ise bazen url'de "istatistikler", "veriler" gibi kelimeler geçebilir. 
        # Katı bir eleme yerine kelime bazlı esnek bir arama yapılır.
        before = len(filtered)
        filtered = [
            f for f in filtered
            if cat_lower in f.get("link_text", "").lower() or
            cat_lower in f.get("url", "").lower() or
            any(word in f.get("url", "").lower() for word in cat_lower.split())
        ]
        
        # Eğer filtre tüm dosyaları eliyorsa, çok katı davranmış olabilir. 
        # Kullanıcı deneyimi için, her şey eleniyorsa fallback olarak filtreyi uygulamayız.
        if len(filtered) == 0 and before > 0:
            reasons.append(f"Kategori filtresi ({category}) tüm {before} dosyayı elediği için koruma amaçlı iptal edildi.")
            filtered = [f for f in files] # Orijinal listeye geri dön
        else:
            excluded = before - len(filtered)
            if excluded > 0:
                reasons.append(f"{excluded} dosya kategori filtresi ({category}) ile hariç tutuldu")

    # Dosya türü filtresi
    file_type = user_filters.get("file_type")
    if file_type and file_type != "all":
        ext = f".{file_type}" if not file_type.startswith(".") else file_type
        before = len(filtered)
        filtered = [f for f in filtered if f.get("extension", "").lower() == ext.lower()]
        excluded = before - len(filtered)
        if excluded > 0:
            reasons.append(f"{excluded} dosya tür filtresi ({file_type}) ile hariç tutuldu")

    return filtered


# Dynamic download URL patterns (uzantısız dosya linkleri)
DOWNLOAD_URL_PATTERNS = [
    r"DownloadDocument",
    r"download\?",
    r"dosya-indir",
    r"file/download",
    r"getfile",
    r"attachment",
    r"export",     # Export links
    r"/rapor/",    # Rapor links
    r"document\.pdf", # Known static generated links
    r"data/file",  # Data files
    r"excel\?",    # Excel dynamic routers
]

# Dosya türü ipuçları — link text, title veya image src'den
FILE_TYPE_HINTS = {
    "word": (".docx", "document"),
    "docx": (".docx", "document"),
    "doc": (".docx", "document"),
    "excel": (".xlsx", "spreadsheet"),
    "xlsx": (".xlsx", "spreadsheet"),
    "xls": (".xlsx", "spreadsheet"),
    "pdf": (".pdf", "pdf"),
    "csv": (".csv", "spreadsheet"),
}


def detect_download_link(href: str) -> bool:
    """URL'nin dinamik bir indirme linki olup olmadığını kontrol eder."""
    href_lower = href.lower()
    for pattern in DOWNLOAD_URL_PATTERNS:
        if re.search(pattern, href_lower, re.IGNORECASE):
            return True
    return False


def infer_file_type_from_context(link: dict) -> tuple[str, str]:
    """
    Link text, title veya image src'den dosya türünü çıkarır.
    Returns: (extension, file_type) tuple
    """
    # Tüm bağlamı birleştir
    context = " ".join([
        link.get("text", ""),
        link.get("title", ""),
        link.get("href", ""),
    ]).lower()

    for hint_key, (ext, ftype) in FILE_TYPE_HINTS.items():
        if hint_key in context:
            return ext, ftype

    return "", "unknown"


def generate_filename_from_title(link: dict, ext: str) -> str:
    """Link title veya text'ten dosya adı üretir."""
    title = link.get("title", "") or link.get("text", "")
    if title:
        # Türkçe karakterleri koru, özel karakterleri temizle
        clean = re.sub(r'[^\w\s\-çğıöşüÇĞİÖŞÜ]', '', title)
        clean = re.sub(r'\s+', '_', clean.strip())
        if clean:
            return f"{clean[:80]}{ext}"
    return f"document{ext}"


async def link_extractor_node(state: AgentState) -> dict:
    """
    Ham linklerden indirilebilir dosyaları ayıklar.
    Kullanıcı filtrelerini uygular.

    İki keşif stratejisi:
    1. Extension-based: URL'de .xlsx, .pdf gibi uzantı olanlar
    2. Dynamic download: /DownloadDocument?id=, /download? gibi pattern'ler

    Bu node deterministik çalışır — LLM kullanmaz.
    """
    base_url = state["url"]
    raw_links = state.get("raw_links", [])
    user_filters = state.get("user_filters", {})

    logger.info(f"🔍 Link analizi başlıyor: {len(raw_links)} ham link")

    downloadable = []
    seen_urls = set()

    for link in raw_links:
        href = link.get("href", "")
        if not href:
            continue

        abs_url = resolve_url(base_url, href)
        if not abs_url or abs_url in seen_urls:
            continue

        link_text = link.get("text", "").strip()
        link_title = link.get("title", "").strip()

        # Strateji 1: Extension-based (geleneksel)
        ext = get_extension(abs_url)
        if ext in SUPPORTED_EXTENSIONS:
            seen_urls.add(abs_url)
            downloadable.append({
                "url": abs_url,
                "filename": extract_filename(abs_url),
                "extension": ext,
                "file_type": classify_file_type(ext),
                "link_text": link_title or link_text,
                "period": detect_period(link_title or link_text, abs_url),
                "category": None,
            })
            continue

        # Strateji 2: Dynamic download URL pattern (EPDK gibi siteler)
        if detect_download_link(abs_url):
            inferred_ext, inferred_type = infer_file_type_from_context(link)
            if inferred_type == "unknown":
                # Bilinmeyen tür olsa bile download linki olarak kabul et
                inferred_ext = ""
                inferred_type = "document"

            seen_urls.add(abs_url)
            filename = generate_filename_from_title(link, inferred_ext)

            downloadable.append({
                "url": abs_url,
                "filename": filename,
                "extension": inferred_ext,
                "file_type": inferred_type,
                "link_text": link_title or link_text,
                "period": detect_period(link_title or link_text, abs_url),
                "category": None,
            })

    total_found = len(downloadable)
    logger.info(f"📎 {total_found} indirilebilir dosya bulundu")

    # 2. Kullanıcı filtrelerini uygula
    if user_filters and any(v for v in user_filters.values() if v):
        filtered = apply_filters(downloadable, user_filters, state.get("page_meta"))
    else:
        filtered = downloadable

    logger.info(f"📋 Filtre sonrası: {len(filtered)} dosya")

    if not filtered:
        filter_desc = ", ".join(
            f"{k}={v}" for k, v in (user_filters or {}).items() if v
        )
        return {
            "error": (
                f"Belirtilen kriterlere uygun dosya bulunamadı. "
                f"Toplam {total_found} dosya bulundu ama filtreler ({filter_desc}) "
                f"tümünü eledi. Filtreyi genişletmeyi deneyin."
            ),
            "phase": "failed",
            "file_list": [],
        }

    return {
        "file_list": filtered,
        "phase": "files_discovered",
    }

