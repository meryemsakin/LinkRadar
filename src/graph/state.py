"""
LangGraph State Definitions
Tüm agent node'ları arasında paylaşılan state tanımları.
"""
from __future__ import annotations

from typing import TypedDict, Annotated, Literal, Optional, List
import operator


class UserFilters(TypedDict, total=False):
    """Kullanıcı tarafından belirtilen filtreleme parametreleri."""
    year: Optional[str]
    month: Optional[str]
    category: Optional[str]
    file_type: Optional[str]


class FileInfo(TypedDict):
    """Keşfedilen tek bir dosyanın bilgileri."""
    url: str
    filename: str
    extension: str
    file_type: str  # "spreadsheet", "document", "pdf", "archive", "other"
    period: Optional[str]
    category: Optional[str]
    link_text: str


class AnalyzedFile(TypedDict, total=False):
    """Analiz edilmiş tek bir dosyanın tam bilgileri."""
    url: str
    filename: str
    extension: str
    file_type: str
    period: Optional[str]
    category: Optional[str]
    summary: str
    metadata: dict
    status: str  # "success", "error", "skipped"
    error_message: Optional[str]
    size_bytes: Optional[int]


class PageMeta(TypedDict, total=False):
    """Sayfa analiz sonucu: kurum, sektör, yapı bilgileri."""
    institution: str
    sector: str
    content_type: str
    organization_scheme: str
    available_dimensions: List[dict]
    language: str
    confidence: float


def merge_analyzed_files(existing: List[AnalyzedFile], new: List[AnalyzedFile]) -> List[AnalyzedFile]:
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
    raw_links: List[dict]
    page_meta: PageMeta

    # Intermediate - dosya keşfi
    file_list: List[FileInfo]

    # Output - analiz sonuçları (paralel birleştirme için reducer)
    analyzed_files: Annotated[List[AnalyzedFile], merge_analyzed_files]

    # Control
    phase: str  # "init", "analyzed", "files_discovered", "processing", "complete", "failed"
    error: Optional[str]

    # Feedback loop (verifier → re-analysis)
    retry_count: int
    needs_retry: bool
    retry_reason: Optional[str]
    verification_issues: List[str]

    # Human-in-the-loop
    awaiting_confirmation: bool
    user_confirmation: Optional[str]


class FileAnalysisState(TypedDict):
    """Tek bir dosyanın analizi için izole state (Send API ile)."""
    file_info: FileInfo
    job_id: str
