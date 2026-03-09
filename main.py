from __future__ import annotations
"""
Dosya Keşif ve Analiz Sistemi — CLI Giriş Noktası
Typer ile komut satırı arayüzü.
Doğal dil sorgusu veya explicit filtreler kabul eder.
"""

import asyncio
import uuid
import logging
import os
import sys

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

# .env yükle
load_dotenv()

console = Console()
app = typer.Typer(
    name="file-discovery",
    help="Verilen URL'deki indirilebilir dosyaları keşfeder, kategorize eder ve özetler.",
    add_completion=False,
)


def setup_logging(verbose: bool = False):
    """Logging yapılandırması."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


@app.command()
def analyze(
    url: str = typer.Argument(
        ...,
        help="Analiz edilecek web sayfasının URL'si",
    ),
    query: str = typer.Option(
        None, "--query", "-q",
        help="Doğal dil sorgusu (örn: '2025 yılına ait Excel raporlarını listele')",
    ),
    year: str = typer.Option(
        None, "--year", "-y",
        help="Yıl filtresi (örn: 2025)",
    ),
    month: str = typer.Option(
        None, "--month", "-m",
        help="Ay filtresi (örn: Ocak veya 01)",
    ),
    category: str = typer.Option(
        None, "--category", "-c",
        help="Kategori filtresi (örn: Petrol)",
    ),
    file_type: str = typer.Option(
        None, "--file-type", "-t",
        help="Dosya türü filtresi (xlsx, pdf, docx, all)",
    ),
    output: str = typer.Option(
        None, "--output", "-o",
        help="Sonuçları JSON olarak kaydet (örn: examples/epdk_2025.json)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Detaylı log çıktısı",
    ),
):
    """
    Verilen URL'deki indirilebilir dosyaları otomatik olarak tespit eder,
    kategorize eder ve içeriklerini özetler.

    İki kullanım modu:

    1. Doğal dil sorgusu:
        python main.py "https://epdk.gov.tr/..." -q "2025 yılına ait raporları listele"

    2. Explicit filtreler:
        python main.py "https://epdk.gov.tr/..." --year 2025 --file-type xlsx
    """
    setup_logging(verbose)

    # API key kontrolü
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        console.print(
            "[red]❌ API key bulunamadı![/red]\n"
            "[dim]1. .env.example dosyasını .env olarak kopyalayın[/dim]\n"
            "[dim]2. OPENAI_API_KEY veya GOOGLE_API_KEY değerini ekleyin[/dim]"
        )
        raise typer.Exit(code=1)

    # Filtreleri hazırla
    if query:
        # Doğal dil sorgusu → filtre çıkarımı
        console.print(f"\n[bold cyan]🚀 Dosya Keşif ve Analiz Sistemi[/bold cyan]")
        console.print(f"[dim]URL: {url}[/dim]")
        console.print(f"[dim]Sorgu: \"{query}\"[/dim]")
        console.print(f"[dim]Filtreler çıkarılıyor...[/dim]")
        user_filters = asyncio.run(_parse_query(query))
        if user_filters:
            filter_str = ", ".join(f"{k}={v}" for k, v in user_filters.items())
            console.print(f"[green]✅ Çıkarılan filtreler: {filter_str}[/green]")
        else:
            console.print(f"[yellow]⚠️ Filtre çıkarılamadı, tüm dosyalar listelenecek[/yellow]")
    else:
        # Explicit filtreler
        user_filters = {
            "year": year,
            "month": month,
            "category": category,
            "file_type": file_type,
        }
        user_filters = {k: v for k, v in user_filters.items() if v is not None}

        console.print(f"\n[bold cyan]🚀 Dosya Keşif ve Analiz Sistemi[/bold cyan]")
        console.print(f"[dim]URL: {url}[/dim]")
        if user_filters:
            filter_str = ", ".join(f"{k}={v}" for k, v in user_filters.items())
            console.print(f"[dim]Filtreler: {filter_str}[/dim]")

    console.print()

    # Graph'ı çalıştır
    try:
        result = asyncio.run(_run_graph(url, user_filters))
        _display_result(result)

        # JSON çıktı kaydet
        if output:
            _save_json_output(result, output)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ İşlem kullanıcı tarafından iptal edildi.[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print(f"\n[red]❌ Beklenmeyen hata: {str(e)}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1)


async def _parse_query(query: str) -> dict:
    """Doğal dil sorgusundan filtre çıkarır."""
    from src.agents.query_parser import parse_user_query
    return await parse_user_query(query)


async def _run_graph(url: str, user_filters: dict) -> dict:
    """LangGraph'ı async olarak çalıştırır."""
    from src.graph.graph_builder import build_graph

    graph = build_graph()

    initial_state = {
        "url": url,
        "user_filters": user_filters,
        "job_id": str(uuid.uuid4())[:8],
        "phase": "init",
        "error": None,
        "analyzed_files": [],
        "retry_count": 0,
    }

    # Graph'ı çalıştır ve son state'i al
    final_state = None
    async for event in graph.astream(initial_state):
        for node_name, node_output in event.items():
            if isinstance(node_output, dict):
                if final_state is None:
                    final_state = {**initial_state}
                final_state.update(node_output)

    return final_state or initial_state


def _display_result(state: dict):
    """Sonuçları terminale yazdırır."""
    from src.formatters.output_formatter import format_output
    output = format_output(state)
    console.print(output)


def _save_json_output(state: dict, filepath: str):
    """Analiz sonuçlarını JSON olarak kaydeder."""
    import json
    from pathlib import Path

    # Kaydedilecek alanları seç (state'in tamamı değil, sadece sonuçlar)
    output_data = {
        "url": state.get("url", ""),
        "filters": state.get("user_filters", {}),
        "page_meta": state.get("page_meta", {}),
        "total_files": len(state.get("analyzed_files", [])),
        "successful": sum(1 for f in state.get("analyzed_files", []) if f.get("status") == "success"),
        "failed": sum(1 for f in state.get("analyzed_files", []) if f.get("status") == "error"),
        "verification_issues": state.get("verification_issues", []),
        "files": [
            {
                "filename": f.get("filename", ""),
                "url": f.get("url", ""),
                "extension": f.get("extension", ""),
                "file_type": f.get("file_type", ""),
                "period": f.get("period"),
                "summary": f.get("summary", ""),
                "status": f.get("status", ""),
                "size_bytes": f.get("size_bytes", 0),
                "error_message": f.get("error_message"),
            }
            for f in state.get("analyzed_files", [])
        ],
    }

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as fp:
        json.dump(output_data, fp, ensure_ascii=False, indent=2)

    console.print(f"\n[green]💾 Sonuçlar kaydedildi: {filepath}[/green]")


if __name__ == "__main__":
    app()
