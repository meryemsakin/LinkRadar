"""
Output Formatter
Rich kütüphanesi ile hiyerarşik terminal çıktısı.
"""
from __future__ import annotations

from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from collections import defaultdict


console = Console()


def format_size(size_bytes: int | None) -> str:
    """Byte cinsinden boyutu okunaklı formata çevirir."""
    if not size_bytes:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def get_file_icon(file_type: str) -> str:
    """Dosya türüne göre emoji döndürür."""
    icons = {
        "spreadsheet": "📊",
        "document": "📄",
        "pdf": "📕",
        "archive": "📦",
        "text": "📝",
        "data": "💾",
    }
    return icons.get(file_type, "📎")


def format_output(state: dict) -> str:
    """
    Analiz sonuçlarını hiyerarşik formatta terminal çıktısına dönüştürür.
    Rich Panel ve Tree kullanarak görsel çıktı üretir.
    """
    page_meta = state.get("page_meta", {})
    analyzed_files = state.get("analyzed_files", [])
    user_filters = state.get("user_filters", {})
    error = state.get("error")
    phase = state.get("phase", "unknown")

    output_lines = []

    # Başlık
    institution = page_meta.get("institution", "Bilinmeyen Kurum")
    content_type = page_meta.get("content_type", "")
    sector = page_meta.get("sector", "")

    output_lines.append("━" * 60)
    output_lines.append(f"📊 Kaynak: {institution}" + (f" — {content_type}" if content_type else ""))
    if sector and sector != "unknown":
        output_lines.append(f"🏛️  Sektör: {sector}")

    # Filtreler
    active_filters = []
    if user_filters:
        if user_filters.get("year"):
            active_filters.append(f"Yıl → {user_filters['year']}")
        if user_filters.get("month"):
            active_filters.append(f"Ay → {user_filters['month']}")
        if user_filters.get("category"):
            active_filters.append(f"Kategori → {user_filters['category']}")
        if user_filters.get("file_type") and user_filters["file_type"] != "all":
            active_filters.append(f"Tür → {user_filters['file_type']}")

    if active_filters:
        output_lines.append(f"🔍 Filtre: {', '.join(active_filters)}")

    output_lines.append("")

    # Hata durumu
    if phase == "failed" and error:
        output_lines.append(f"❌ Hata: {error}")
        output_lines.append("━" * 60)
        return "\n".join(output_lines)

    if not analyzed_files:
        output_lines.append("ℹ️  Analiz edilecek dosya bulunamadı.")
        output_lines.append("━" * 60)
        return "\n".join(output_lines)

    # Dosyaları döneme göre grupla
    groups = defaultdict(list)
    for f in analyzed_files:
        period = f.get("period") or "Dönemi Belirtilmemiş"
        groups[period].append(f)

    # Grupları sırala
    for period in sorted(groups.keys()):
        files = groups[period]

        # Dönem başlığı
        if period != "Dönemi Belirtilmemiş":
            # "2025-01" → "2025 / Ocak" formatına çevir
            display_period = _format_period(period)
        else:
            display_period = period

        output_lines.append(f"📁 {display_period}")

        for i, f in enumerate(files):
            is_last = i == len(files) - 1
            prefix = "  └── " if is_last else "  ├── "
            detail_prefix = "        └── " if is_last else "  │     └── "

            icon = get_file_icon(f.get("file_type", ""))
            filename = f.get("filename", "unknown")
            size = format_size(f.get("size_bytes"))
            size_str = f"  [{size}]" if size else ""

            status = f.get("status", "unknown")

            if status == "success":
                output_lines.append(f"{prefix}{icon} {filename}{size_str}")
                summary = f.get("summary", "")
                if summary:
                    # Özeti satırlara böl ve indent'le
                    summary_lines = summary.split("\n")
                    for j, line in enumerate(summary_lines[:3]):  # Max 3 satır
                        if j == 0:
                            output_lines.append(f"{detail_prefix}{line.strip()}")
                        else:
                            output_lines.append(f"              {line.strip()}")
            elif status == "error":
                err_msg = f.get("error_message", "Bilinmeyen hata")
                output_lines.append(f"{prefix}⚠️  {filename}{size_str}")
                output_lines.append(f"{detail_prefix}{err_msg}")

        output_lines.append("")

    # İstatistikler
    successful = sum(1 for f in analyzed_files if f.get("status") == "success")
    failed = sum(1 for f in analyzed_files if f.get("status") == "error")
    total = len(analyzed_files)

    if failed > 0:
        output_lines.append(
            f"⚠️  {failed}/{total} dosya analiz edilemedi"
        )
    output_lines.append(f"✅ {successful}/{total} dosya başarıyla analiz edildi")
    output_lines.append("━" * 60)

    return "\n".join(output_lines)


def _format_period(period: str) -> str:
    """Dönem string'ini okunaklı formata çevirir."""
    MONTH_NAMES = {
        "01": "Ocak", "02": "Şubat", "03": "Mart", "04": "Nisan",
        "05": "Mayıs", "06": "Haziran", "07": "Temmuz", "08": "Ağustos",
        "09": "Eylül", "10": "Ekim", "11": "Kasım", "12": "Aralık",
    }

    if "-" in period:
        parts = period.split("-")
        if len(parts) == 2:
            year = parts[0]
            month = MONTH_NAMES.get(parts[1], parts[1])
            return f"{year} / {month}"
    return period


def print_output(state: dict):
    """Formatlanmış çıktıyı terminale yazdırır."""
    output = format_output(state)
    console.print(output)
