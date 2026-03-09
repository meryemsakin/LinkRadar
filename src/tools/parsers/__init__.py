from __future__ import annotations
"""
Parsers Package
Dosya türüne göre uygun parser'ı seçen dispatcher.
"""

from .excel_parser import parse_excel
from .word_parser import parse_word
from .pdf_parser import parse_pdf


PARSER_MAP = {
    ".xlsx": parse_excel,
    ".xls": parse_excel,
    ".docx": parse_word,
    ".doc": parse_word,
    ".pdf": parse_pdf,
}


async def parse_file(file_bytes: bytes, extension: str, filename: str = "") -> dict:
    """
    Dosya uzantısına göre uygun parser'ı seçer ve çalıştırır.

    Args:
        file_bytes: Dosyanın ham byte içeriği
        extension: Dosya uzantısı (örn: ".xlsx")
        filename: Dosya adı (loglama için)

    Returns:
        Parser sonucu dict veya desteklenmeyen format hatası
    """
    ext = extension.lower()
    parser = PARSER_MAP.get(ext)

    if parser is None:
        # CSV dosyaları için basit metadata
        if ext == ".csv":
            return await _parse_csv(file_bytes, filename)
        return {
            "success": False,
            "error": f"Desteklenmeyen dosya formatı: {ext}",
        }

    return await parser(file_bytes, filename)


async def _parse_csv(file_bytes: bytes, filename: str) -> dict:
    """CSV dosyası için basit metadata çıkarımı."""
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        lines = text.strip().split("\n")

        # İlk satır: başlıklar
        headers = lines[0].split(",") if lines else []
        headers = [h.strip().strip('"') for h in headers]

        # İlk 3 veri satırı
        sample_rows = []
        for line in lines[1:4]:
            cells = line.split(",")
            sample_rows.append([c.strip().strip('"')[:50] for c in cells])

        return {
            "success": True,
            "sheets": [{
                "sheet_name": "CSV",
                "column_headers": headers,
                "sample_rows": sample_rows,
                "total_rows": len(lines),
                "total_columns": len(headers),
            }],
            "total_sheets": 1,
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "sheets": [],
            "total_sheets": 0,
            "error": f"CSV parse hatası: {str(e)}",
        }
