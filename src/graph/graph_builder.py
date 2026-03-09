from __future__ import annotations
"""
Graph Builder — Agentic Architecture v2
StateGraph tanımı — verifier feedback loop ve conditional routing.

Graph yapısı:
START → page_analyzer → structure_mapper → filter_confirm
      → link_extractor → content_analyzer → verifier
      → (conditional) → result_formatter → END
                       ↗ (retry) → link_extractor (feedback loop)
"""

import logging
from langgraph.graph import StateGraph, START, END

from src.graph.state import AgentState
from src.agents.web_analyst import (
    page_analyzer_node,
    structure_mapper_node,
    filter_confirm_node,
)
from src.agents.file_scout import link_extractor_node
from src.agents.content_analyst import content_analyzer_node, error_handler_node
from src.agents.verifier import verifier_node
from src.graph.routers import (
    route_after_analysis,
    route_after_link_extraction,
    route_after_verification,
)

logger = logging.getLogger(__name__)


async def result_formatter_node(state: AgentState) -> dict:
    """
    Tüm analiz sonuçlarını birleştirir ve son çıktıyı hazırlar.
    Verifier'dan gelen uyarıları da dahil eder.
    """
    analyzed_files = state.get("analyzed_files", [])
    verification_issues = state.get("verification_issues", [])

    successful = [f for f in analyzed_files if f.get("status") == "success"]
    failed = [f for f in analyzed_files if f.get("status") == "error"]

    logger.info(
        f"📊 Sonuçlar: {len(successful)} başarılı, {len(failed)} başarısız "
        f"— toplam {len(analyzed_files)} dosya"
    )

    if verification_issues:
        logger.info(f"🔍 Verifier uyarıları: {len(verification_issues)}")

    return {
        "phase": "complete",
    }


def build_graph():
    """
    Agentic LangGraph graph'ı — verifier feedback loop dahil.

    Akış:
    START → page_analyzer → (conditional) → structure_mapper → filter_confirm
           → link_extractor → (conditional) → content_analyzer
           → verifier → (conditional) → result_formatter → END
                                       → link_extractor (retry loop)

    Hata durumlarında:
    page_analyzer veya link_extractor → error_handler → END
    """
    graph = StateGraph(AgentState)

    # Node'ları ekle
    graph.add_node("page_analyzer_node", page_analyzer_node)
    graph.add_node("structure_mapper_node", structure_mapper_node)
    graph.add_node("filter_confirm_node", filter_confirm_node)
    graph.add_node("link_extractor_node", link_extractor_node)
    graph.add_node("content_analyzer_node", content_analyzer_node)
    graph.add_node("verifier_node", verifier_node)
    graph.add_node("result_formatter_node", result_formatter_node)
    graph.add_node("error_handler_node", error_handler_node)

    # ─── Edges ────────────────────────────────────────────

    # START → page_analyzer
    graph.add_edge(START, "page_analyzer_node")

    # page_analyzer → (conditional) → structure_mapper veya error_handler
    graph.add_conditional_edges(
        "page_analyzer_node",
        route_after_analysis,
    )

    # structure_mapper → filter_confirm → link_extractor
    graph.add_edge("structure_mapper_node", "filter_confirm_node")
    graph.add_edge("filter_confirm_node", "link_extractor_node")

    # link_extractor → (conditional) → content_analyzer veya error_handler
    graph.add_conditional_edges(
        "link_extractor_node",
        route_after_link_extraction,
        {
            "content_analyzer_node": "content_analyzer_node",
            "error_handler_node": "error_handler_node",
        },
    )

    # content_analyzer → verifier (quality gate)
    graph.add_edge("content_analyzer_node", "verifier_node")

    # verifier → (conditional) → result_formatter VEYA link_extractor (retry)
    graph.add_conditional_edges(
        "verifier_node",
        route_after_verification,
        {
            "result_formatter_node": "result_formatter_node",
            "link_extractor_node": "link_extractor_node",
        },
    )

    # result_formatter → END
    graph.add_edge("result_formatter_node", END)

    # error_handler → END
    graph.add_edge("error_handler_node", END)

    # Graph'ı derle
    compiled = graph.compile()
    return compiled
