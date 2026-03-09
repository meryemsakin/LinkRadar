import gradio as gr
import asyncio
import os
import uuid
from dotenv import load_dotenv

from src.agents.query_parser import parse_user_query
from src.graph.graph_builder import build_graph
from src.formatters.output_formatter import format_output

# Çevresel değişkenleri yükle
load_dotenv()

async def analyze_url(url: str, query: str) -> str:
    """Verilen URL'yi ve sorguyu alıp LangGraph pipeline'ını çalıştırır."""
    if not url:
        return "❌ Lütfen geçerli bir URL girin."
        
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "❌ API Key bulunamadı! Lütfen .env dosyasına OPENAI_API_KEY veya GOOGLE_API_KEY ekleyin."

    try:
        user_filters = await parse_user_query(query) if query else {}
        
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
        
        final_state = None
        async for event in graph.astream(initial_state):
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    if final_state is None:
                        final_state = {**initial_state}
                    final_state.update(node_output)
        
        state = final_state or initial_state
        
        # Sonuçları formatla
        output_text = format_output(state)
        return output_text
        
    except Exception as e:
        return f"❌ Beklenmeyen bir hata oluştu: {str(e)}"

def run_analysis_sync(url: str, query: str) -> str:
    """Gradio'nun senkron çalışması için async fonksiyonu sarmalar."""
    return asyncio.run(analyze_url(url, query))

# Gradio Arayüzü Tasarımı
custom_css = """
/* Vercel / Linear Inspired Dark Theme */
body, .gradio-container {
    background-color: #000000 !important;
    color: #EDEDED !important;
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
}

.gradio-container {
    max-width: 900px !important;
    margin: auto;
    padding-top: 3rem !important;
}

/* Header box */
.header-box {
    text-align: center;
    padding: 3rem 1rem;
    margin-bottom: 2.5rem;
    background: transparent;
    border-radius: 12px;
    border: 1px solid #222222;
    position: relative;
    overflow: hidden;
    /* Subtle glow */
    box-shadow: 0 0 40px rgba(255, 255, 255, 0.03);
}

.header-title {
    font-size: 3rem;
    font-weight: 800;
    margin-bottom: 1rem;
    letter-spacing: -0.06em;
    background: linear-gradient(180deg, #FFFFFF 0%, #999999 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.header-subtitle {
    color: #888888;
    font-size: 1.1rem;
    max-width: 600px;
    margin: 0 auto;
    line-height: 1.5;
    font-weight: 400;
}

/* Base Inputs */
textarea, input {
    background-color: #0A0A0A !important;
    border: 1px solid #333333 !important;
    color: #EDEDED !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    transition: all 0.2s ease !important;
}

textarea:focus, input:focus {
    border-color: #555555 !important;
    box-shadow: 0 0 0 1px #555555 !important;
    outline: none !important;
}

/* Primary Button */
.primary-btn {
    background: #EDEDED !important;
    color: #000000 !important;
    border: none !important;
    font-weight: 600 !important;
    font-size: 1.05rem !important;
    border-radius: 8px !important;
    padding: 0.75rem !important;
    transition: all 0.2s ease !important;
}

.primary-btn:hover {
    background: #FFFFFF !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(255,255,255,0.1) !important;
}

/* Output Console */
.output-console {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    background-color: #0A0A0A;
    color: #EDEDED;
    padding: 1.5rem;
    border-radius: 12px;
    border: 1px solid #333333;
    white-space: pre-wrap;
    min-height: 250px;
    font-size: 0.9rem;
    line-height: 1.6;
}

/* Section titles */
.section-title {
    color: #EDEDED;
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 1rem;
    margin-top: 1rem;
    padding-bottom: 0.75rem;
}

/* Examples */
.examples-gallery {
    margin-top: 3rem !important;
    border-radius: 12px !important;
    border: 1px solid #222222 !important;
    background-color: #050505 !important;
}
"""

with gr.Blocks(title="LinkRadar | Keşif ve Analiz Sistemi") as demo:
    with gr.Column(elem_classes=["gradio-container"]):
        # Header HTML
        gr.HTML("""
        <div class="header-box">
            <div class="header-title">LinkRadar</div>
            <div class="header-subtitle">
                Yapay Zeka Destekli Akıllı Dosya Keşif Motoru.<br>
                Kurumsal portallardaki bilgi yığınından hedef belgeleri saniyeler içinde ayıklayın ve analiz edin.
            </div>
        </div>
        """)
        
        with gr.Row():
            with gr.Column(scale=5):
                url_input = gr.Textbox(
                    label="Hedef URL", 
                    placeholder="https://www.epdk.gov.tr/Detay/Icerik/3-0-104/aylik-sektor-raporu",
                    lines=1
                )
            with gr.Column(scale=4):
                query_input = gr.Textbox(
                    label="Doğal Dil Sorgusu (Opsiyonel)", 
                    placeholder="2025 yılına ait petrol raporlarını bul",
                    lines=1
                )
                
        submit_btn = gr.Button("Analizi Başlat", elem_classes=["primary-btn"])
        
        gr.HTML("<div class='section-title'>Analiz Raporu</div>")
        
        output_display = gr.Markdown(
            elem_classes=["output-console"],
            value="<div style='color: #555555; text-align: center; margin-top: 100px;'>Sistemi çalıştırmak için hedef URL girin ve butona tıklayın</div>"
        )
        
        # Loading State with CSS Animation Effect trick
        def simulate_loading():
            return "<div style='color: #EDEDED; text-align: center; margin-top: 100px;'>Agent'lar analiz yapıyor... Lütfen bekleyin.</div>"

        submit_btn.click(
            fn=simulate_loading, 
            inputs=[], 
            outputs=[output_display]
        ).then(
            fn=run_analysis_sync, 
            inputs=[url_input, query_input], 
            outputs=[output_display]
        )
        
        gr.Examples(
            examples=[
                ["https://www.epdk.gov.tr/Detay/Icerik/3-0-104/aylik-sektor-raporu", "2025 yılına ait petrol raporları"],
                ["https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Istatistikler/Enflasyon+Verileri/", "Tüm enflasyon verileri listesi (excel)"]
            ],
            inputs=[url_input, query_input],
            label="Örnek Vaka Çalışmaları"
        )
        
        gr.HTML("""
        <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #222; color: #555; font-size: 0.85rem;">
            LinkRadar &bull; AI Agentic Workflow Concept
        </div>
        """)

if __name__ == "__main__":
    print("🚀 LinkRadar Web UI Başlatılıyor...")
    import gradio as gr_module
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, css=custom_css, theme=gr_module.themes.Base())

