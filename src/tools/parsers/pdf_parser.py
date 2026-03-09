from __future__ import annotations
"""
PDF Parser — Adaptive Deep Parsing
Sadece ilk sayfaya bakmak yerine, dosyanın yapısal profili çıkarılır.
Büyük dosyalar için stratejik sayfa seçimi yapılır.
"""

import logging

logger = logging.getLogger(__name__)


async def parse_pdf(file_bytes: bytes, filename: str = "") -> dict:
    """
    PDF dosyasından metadata ve içerik önizlemesi çıkarır.

    Adaptive strategy:
    - İlk 3 sayfa → yapı analizi (başlık, TOC)
    - Ortadaki 2 sayfa → çekirdek içerik
    - Son sayfa → sonuç/özet tespiti
    - Tüm tablolar → tablo sayısı ve yapısı
    """
    try:
        import pdfplumber
        from io import BytesIO

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            total_pages = len(pdf.pages)

            if total_pages == 0:
                return {"success": False, "error": "PDF boş — sayfa yok"}

            # ─── Adaptive sayfa seçimi ────────────────────
            selected_pages = set()

            # İlk 3 sayfa (yapı & giriş)
            for i in range(min(3, total_pages)):
                selected_pages.add(i)

            # Ortadaki 2 sayfa (çekirdek içerik)
            if total_pages > 6:
                mid = total_pages // 2
                selected_pages.add(mid - 1)
                selected_pages.add(mid)

            # Son 2 sayfa (sonuç/özet)
            if total_pages > 3:
                selected_pages.add(total_pages - 1)
                if total_pages > 4:
                    selected_pages.add(total_pages - 2)

            # ─── Sayfa processing ─────────────────────────
            page_previews = []
            all_tables_info = []
            total_chars = 0

            for page_idx in sorted(selected_pages):
                page = pdf.pages[page_idx]
                text = page.extract_text() or ""
                total_chars += len(text)

                # Sayfa preview (ilk 500 char)
                preview = text[:500].strip()
                if preview:
                    page_previews.append({
                        "page": page_idx + 1,
                        "position": _page_position(page_idx, total_pages),
                        "preview": preview,
                    })

                # Tablo tespiti
                tables = page.extract_tables() or []
                for table in tables:
                    if table and len(table) > 0:
                        # Sadece başlık satırı + ilk 3 veri satırı
                        header = table[0] if table else []
                        sample_rows = table[1:4] if len(table) > 1 else []
                        all_tables_info.append({
                            "page": page_idx + 1,
                            "rows": len(table),
                            "cols": len(header) if header else 0,
                            "header": [str(c)[:30] for c in header if c] if header else [],
                            "sample_rows": [
                                [str(c)[:30] for c in row if c] for row in sample_rows
                            ],
                        })

            return {
                "success": True,
                "format": "pdf",
                "total_pages": total_pages,
                "sampled_pages": len(selected_pages),
                "sampling_strategy": "adaptive" if total_pages > 6 else "full",
                "estimated_chars": total_chars,
                "page_previews": page_previews,
                "tables": all_tables_info[:10],  # Max 10 tablo bilgisi
                "table_count": sum(
                    len(page.extract_tables() or [])
                    for page in pdf.pages
                ),
            }

    except Exception as e:
        logger.error(f"PDF parse hatası: {filename} — {str(e)}")
        return {"success": False, "error": f"PDF parse hatası: {str(e)}"}


def _page_position(idx: int, total: int) -> str:
    """Sayfa pozisyonunu semantic label olarak döner."""
    if idx == 0:
        return "başlangıç"
    elif idx < 3:
        return "giriş"
    elif idx >= total - 2:
        return "son"
    else:
        return "orta"
