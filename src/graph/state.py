"""
LangGraph State Definitions
Tüm agent node'ları arasında paylaşılan state tanımları.
"""
from __future__ import annotations

from typing import TypedDict, Annotated, Literal
import operator


class UserFilters(TypedDict, total=False):
    """Kullanıcı tarafından belirtilen filtreleme parametreleri."""
    year: str | None
    month: str | None
    category: str | None
    file_type: str | None


class FileInfo(TypedDict):
    """Keşfedilen tek bir dosyanın bilgileri."""
    url: str
    filename: str
    extension: str
    file_type: str  # "spreadsheet", "document", "pdf", "archive", "other"
    period: str | None
    category: str | None
    link_text: str


class AnalyzedFile(TypedDict, total=False):
    """Analiz edilmiş tek bir dosyanın tam bilgileri."""
    url: str
    filename: str
    extension: str
    file_type: str
    period: str | None
    category: str | None
    summary: str
    metadata: dict
    status: str  # "success", "error", "skipped"
    error_message: str | None
    size_bytes: int | None


class PageMeta(TypedDict, total=False):
    """Sayfa analiz sonucu: kurum, sektör, yapı bilgileri."""
    institution: str
    sector: str
    content_type: str
    organization_scheme: str
    available_dimensions: list[dict]
    language: str
    confidence: float


def merge_analyzed_files(existing: list[AnalyzedFile], new: list[AnalyzedFile]) -> list[AnalyzedFile]:
    """Paralel content analyzer node'larından gelen sonuçları birleştirir."""
    if existing is None:
        return new or []
    if new is None:
        return existing or []
    return existing + new


class AgentState(TypedDict, total=False):
    """Ana graph state: tüm node'lar arasında paylaşılır."""
    # Input
    url: str
    user_filters: UserFilters
    job_id: str

    # Intermediate - crawl sonuçları
    page_markdown: str
    raw_links: list[dict]
    page_meta: PageMeta

    # Intermediate - dosya keşfi
    file_list: list[FileInfo]

    # Output - analiz sonuçları (paralel birleştirme için reducer)
    analyzed_files: Annotated[list[AnalyzedFile], merge_analyzed_files]

    # Control
    phase: str  # "init", "analyzed", "files_discovered", "processing", "complete", "failed"
    error: str | None

    # Feedback loop (verifier → re-analysis)
    retry_count: int
    needs_retry: bool
    retry_reason: str | None
    verification_issues: list[str]

    # Human-in-the-loop
    awaiting_confirmation: bool
    user_confirmation: str | None


class FileAnalysisState(TypedDict):
    """Tek bir dosyanın analizi için izole state (Send API ile)."""
    file_info: FileInfo
    job_id: str
