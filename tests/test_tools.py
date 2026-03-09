"""
Tool Unit Tests
URL resolution, extension detection, file type classification testleri.
"""

import pytest
from src.agents.file_scout import (
    resolve_url,
    get_extension,
    extract_filename,
    classify_file_type,
    detect_period,
    apply_filters,
    SUPPORTED_EXTENSIONS,
)


class TestResolveUrl:
    def test_absolute_url(self):
        assert resolve_url("https://example.com", "https://other.com/file.xlsx") == "https://other.com/file.xlsx"

    def test_relative_url(self):
        result = resolve_url("https://example.com/page/", "/download/file.pdf")
        assert result == "https://example.com/download/file.pdf"

    def test_relative_path(self):
        result = resolve_url("https://example.com/page/index.html", "file.xlsx")
        assert result == "https://example.com/page/file.xlsx"

    def test_empty_href(self):
        assert resolve_url("https://example.com", "") == ""

    def test_protocol_relative(self):
        result = resolve_url("https://example.com", "//cdn.example.com/file.pdf")
        assert result == "https://cdn.example.com/file.pdf"


class TestGetExtension:
    def test_xlsx(self):
        assert get_extension("https://example.com/report.xlsx") == ".xlsx"

    def test_pdf(self):
        assert get_extension("https://example.com/doc.pdf") == ".pdf"

    def test_with_query(self):
        assert get_extension("https://example.com/report.xlsx?id=123") == ".xlsx"

    def test_no_extension(self):
        assert get_extension("https://example.com/page") == ""

    def test_unsupported_extension(self):
        assert get_extension("https://example.com/image.png") == ""

    def test_encoded_url(self):
        assert get_extension("https://example.com/rapor%202025.pdf") == ".pdf"


class TestExtractFilename:
    def test_simple(self):
        assert extract_filename("https://example.com/report.xlsx") == "report.xlsx"

    def test_nested_path(self):
        assert extract_filename("https://example.com/a/b/c/file.pdf") == "file.pdf"


class TestClassifyFileType:
    def test_spreadsheet(self):
        assert classify_file_type(".xlsx") == "spreadsheet"
        assert classify_file_type(".csv") == "spreadsheet"

    def test_document(self):
        assert classify_file_type(".docx") == "document"

    def test_pdf(self):
        assert classify_file_type(".pdf") == "pdf"

    def test_archive(self):
        assert classify_file_type(".zip") == "archive"


class TestDetectPeriod:
    def test_year_month(self):
        period = detect_period("Ocak 2025 Raporu", "https://example.com/2025/01/report.xlsx")
        assert period is not None
        assert "2025" in period

    def test_year_only(self):
        period = detect_period("2025 Raporu", "https://example.com/report.xlsx")
        assert period == "2025"

    def test_no_period(self):
        period = detect_period("Rapor", "https://example.com/report.xlsx")
        assert period is None

    def test_turkish_month(self):
        period = detect_period("Şubat Raporu 2025", "")
        assert period is not None
        assert "2025" in period
        assert "02" in period


class TestApplyFilters:
    def _make_files(self):
        return [
            {"url": "https://example.com/2025/01/report.xlsx", "filename": "report_2025_01.xlsx",
             "extension": ".xlsx", "file_type": "spreadsheet", "period": "2025-01",
             "link_text": "Ocak 2025 Raporu", "category": None},
            {"url": "https://example.com/2024/12/report.xlsx", "filename": "report_2024_12.xlsx",
             "extension": ".xlsx", "file_type": "spreadsheet", "period": "2024-12",
             "link_text": "Aralık 2024 Raporu", "category": None},
            {"url": "https://example.com/2025/02/doc.pdf", "filename": "doc_2025_02.pdf",
             "extension": ".pdf", "file_type": "pdf", "period": "2025-02",
             "link_text": "Şubat 2025 Belgesi", "category": None},
        ]

    def test_year_filter(self):
        files = self._make_files()
        result = apply_filters(files, {"year": "2025"})
        assert len(result) == 2
        assert all("2025" in f["url"] for f in result)

    def test_file_type_filter(self):
        files = self._make_files()
        result = apply_filters(files, {"file_type": "pdf"})
        assert len(result) == 1
        assert result[0]["extension"] == ".pdf"

    def test_no_filter(self):
        files = self._make_files()
        result = apply_filters(files, {})
        assert len(result) == 3

    def test_combined_filters(self):
        files = self._make_files()
        result = apply_filters(files, {"year": "2025", "file_type": "xlsx"})
        assert len(result) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
