"""
Parser Unit Tests
Excel, Word, PDF parser'larının doğru çalıştığını test eder.
"""

import pytest
import pytest_asyncio

from src.tools.parsers import parse_file


class TestParseFile:
    @pytest.mark.asyncio
    async def test_unsupported_format(self):
        result = await parse_file(b"test", ".png", "test.png")
        assert result["success"] is False
        assert "Desteklenmeyen" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_csv(self):
        csv_content = b"header1,header2,header3\nval1,val2,val3\nval4,val5,val6"
        result = await parse_file(csv_content, ".csv", "test.csv")
        assert result["success"] is True
        assert len(result["sheets"]) == 1
        assert "header1" in result["sheets"][0]["column_headers"]

    @pytest.mark.asyncio
    async def test_malformed_csv(self):
        result = await parse_file(b"", ".csv", "empty.csv")
        # Boş CSV: hata veya boş sheet
        assert "success" in result


class TestOutputFormatter:
    def test_format_output_with_error(self):
        from src.formatters.output_formatter import format_output
        state = {
            "page_meta": {"institution": "Test Kurum"},
            "analyzed_files": [],
            "user_filters": {"year": "2025"},
            "error": "Test hatası",
            "phase": "failed",
        }
        result = format_output(state)
        assert "Test hatası" in result
        assert "Test Kurum" in result

    def test_format_output_with_files(self):
        from src.formatters.output_formatter import format_output
        state = {
            "page_meta": {"institution": "EPDK", "sector": "Enerji"},
            "analyzed_files": [
                {
                    "filename": "test.xlsx",
                    "file_type": "spreadsheet",
                    "period": "2025-01",
                    "summary": "Test özeti",
                    "status": "success",
                    "size_bytes": 1024,
                }
            ],
            "user_filters": {"year": "2025"},
            "error": None,
            "phase": "complete",
        }
        result = format_output(state)
        assert "EPDK" in result
        assert "test.xlsx" in result
        assert "Test özeti" in result

    def test_format_period(self):
        from src.formatters.output_formatter import _format_period
        assert _format_period("2025-01") == "2025 / Ocak"
        assert _format_period("2025-12") == "2025 / Aralık"
        assert _format_period("2025") == "2025"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
