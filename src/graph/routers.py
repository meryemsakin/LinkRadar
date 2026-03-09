from __future__ import annotations
"""
Graph Routers — Conditional edge fonksiyonları
Hata durumları, verifier feedback loop ve akış yönlendirme.
"""

from typing import Literal


def route_after_analysis(state: dict) -> Literal["structure_mapper_node", "error_handler_node"]:
    """
    page_analyzer_node sonrası yönlendirme.
    Başarısızsa error_handler'a, başarılıysa structure_mapper'a.
    """
    if state.get("phase") == "failed":
        return "error_handler_node"
    if not state.get("page_markdown"):
        return "error_handler_node"
    return "structure_mapper_node"


def route_after_link_extraction(state: dict) -> Literal["content_analyzer_node", "error_handler_node"]:
    """
    link_extractor_node sonrası yönlendirme.
    Dosya bulunduysa content_analyzer'a, bulunamadıysa error_handler'a.
    """
    if state.get("phase") == "failed":
        return "error_handler_node"
    if not state.get("file_list"):
        return "error_handler_node"
    return "content_analyzer_node"


def route_after_verification(state: dict) -> Literal["result_formatter_node", "link_extractor_node"]:
    """
    verifier_node sonrası yönlendirme — feedback loop.
    needs_retry True ise link_extractor'a geri dön (re-analysis).
    Aksi halde result_formatter'a devam et.
    """
    if state.get("needs_retry", False) and state.get("retry_count", 0) <= 2:
        return "link_extractor_node"
    return "result_formatter_node"
