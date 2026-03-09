import gradio as gr
import asyncio
import os
import uuid
from dotenv import load_dotenv

from src.agents.query_parser import parse_user_query
from src.graph.graph_builder import build_graph
from src.formatters.output_formatter import format_output

load_dotenv()

async def analyze_url(url: str, query: str) -> str:
    if not url or not url.strip():
        return "❌ Lütfen geçerli bir URL girin."
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "❌ API Key bulunamadı! Lütfen .env dosyasına OPENAI_API_KEY veya GOOGLE_API_KEY ekleyin."
    try:
        user_filters = await parse_user_query(query) if query and query.strip() else {}
        graph = build_graph()
        initial_state = {
            "url": url.strip(),
            "user_filters": user_filters,
            "job_id": str(uuid.uuid4())[:8],
            "phase": "init",
            "error": None,
            "analyzed_files": [],
            "retry_count": 0,
        }
        final_state = None
        async for event in graph.astream(initial_state):
            for _, node_output in event.items():
                if isinstance(node_output, dict):
                    if final_state is None:
                        final_state = {**initial_state}
                    final_state.update(node_output)
        state = final_state or initial_state
        return format_output(state)
    except Exception as e:
        return f"❌ Beklenmeyen bir hata oluştu: `{str(e)}`"


def run_analysis_sync(url: str, query: str) -> str:
    if not url or not url.strip():
        return "❌ Lütfen geçerli bir URL girin."
    try:
        result = asyncio.run(analyze_url(url, query))
        return result
    except Exception as e:
        return f"❌ Beklenmeyen bir hata oluştu: `{str(e)}`"


def simulate_loading():
    return (
        "<span style='color:#C47A3A;font-family:Space Mono,monospace;font-size:.78rem;line-height:2;'>"
        "[INIT] &nbsp; Agent pipeline başlatılıyor...<br>"
        "[01/03] URL crawler aktif — hedef taranıyor...<br>"
        "[02/03] Dosya dedektörü çalışıyor...<br>"
        "[03/03] Sonuçlar filtreleniyor, lütfen bekleyin..."
        "</span>"
    )


# ─────────────────────────────────────────────
#  CSS  —  Refined Tactical Terminal
#  Değişenler vs önceki versiyon:
#  • Siyah → koyu lacivert-gri arka plan (göz yormuyor)
#  • Scanline tamamen kaldırıldı
#  • Dot grid çok daha soluk
#  • Amber daha ılımlı (#C47A3A yerine çığlık #FF6B35)
#  • Padding ve satır aralıkları artırıldı
#  • Kenarlık renkleri yumuşatıldı
# ─────────────────────────────────────────────
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Space+Mono:ital,wght@0,400;0,700;1,400&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

*,*::before,*::after { box-sizing: border-box; }

:root {
  /* Arka planlar — saf siyah yerine mavi-gri tonlar */
  --void:   #0D1117;
  --deep:   #111820;
  --panel:  #141C26;
  --input:  #131B24;

  /* Kenarlıklar — daha soluk */
  --b0: #1E2D3D;
  --b1: #263749;

  /* Aksanlar — amber ılımlılaştırıldı */
  --amber:  #C47A3A;
  --ag:     rgba(196,122,58,.12);
  --ad:     rgba(196,122,58,.05);

  /* Cyan — vurgu için korundu, soluklaştırıldı */
  --cyan:   #4AADCC;
  --cd:     rgba(74,173,204,.07);

  /* Metin */
  --tp: #CDD8E3;   /* primary  — tam beyaz değil, göz dostu */
  --tm: #5A7391;   /* muted    */
  --td: #2A3D52;   /* dim      */

  --ok:  #3DB87A;

  --fd: 'Bebas Neue', sans-serif;
  --fm: 'Space Mono', monospace;
  --fb: 'DM Sans', sans-serif;
}

/* ── BODY ───────────────────── */
body, .gradio-container, .dark, .dark .gradio-container {
  background: var(--void) !important;
  background-image:
    radial-gradient(ellipse 70% 40% at 50% 0%,  rgba(196,122,58,.06) 0%, transparent 60%),
    radial-gradient(ellipse 40% 30% at 90% 95%,  rgba(74,173,204,.04) 0%, transparent 55%)
    !important;
  color: var(--tp) !important;
  font-family: var(--fb) !important;
}

/* Dot grid — çok soluk */
body::after {
  content: '';
  position: fixed; inset: 0;
  background-image: radial-gradient(circle, rgba(196,122,58,.04) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none; z-index: 0;
}

.gradio-container {
  max-width: 1000px !important;
  margin: 0 auto !important;
  padding: 3rem 2rem 5rem !important;
  position: relative; z-index: 1;
}

/* ── HEADER ─────────────────── */
.lk-header {
  display: flex;
  align-items: center;
  gap: 2.8rem;
  padding: 2.8rem 3.2rem;
  margin-bottom: 1.8rem;
  background: var(--deep);
  border: 1px solid var(--b0);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
}
.lk-header::before {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(140deg, rgba(196,122,58,.06) 0%, transparent 50%);
  pointer-events: none;
}
.lk-header::after {
  content: 'BUILD 2025.06';
  position: absolute; top: 14px; right: 18px;
  font-family: var(--fm); font-size: .6rem;
  color: var(--td); letter-spacing: .1em;
}

/* Radar */
.lk-radar { flex-shrink: 0; width: 86px; height: 86px; }
.lk-radar svg { width: 100%; height: 100%; }
.r-ring     { fill: none; stroke: var(--b0); stroke-width: 1; }
.r-ring-hot { fill: none; stroke: var(--amber); stroke-width: .7; opacity: .2; }
.r-sweep    {
  fill: none; stroke: var(--amber); stroke-width: 1.5;
  transform-origin: 43px 43px;
  animation: rspin 3.2s linear infinite;
}
.r-dot { fill: var(--amber); animation: rblink 2.2s ease-in-out infinite; }

@keyframes rspin  { to { transform: rotate(360deg); } }
@keyframes rblink { 0%,100% { opacity: .9; } 50% { opacity: .1; } }

/* Header text */
.lk-htxt { flex: 1; }
.lk-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--ad);
  border: 1px solid rgba(196,122,58,.2);
  border-radius: 3px;
  padding: 3px 10px; margin-bottom: .8rem;
  font-family: var(--fm); font-size: .62rem;
  color: var(--amber); letter-spacing: .12em; text-transform: uppercase;
}
.lk-bdot {
  width: 5px; height: 5px;
  background: var(--amber); border-radius: 50%;
  animation: rblink 1.6s ease-in-out infinite;
}
.lk-title {
  font-family: var(--fd);
  font-size: 3.8rem; letter-spacing: .07em; line-height: 1;
  color: var(--tp); margin-bottom: .5rem;
}
.lk-title b { color: var(--amber); }
.lk-sub {
  font-size: .88rem; color: var(--tm);
  font-weight: 300; line-height: 1.75; max-width: 500px;
}

/* ── STATUS BAR ─────────────── */
.lk-sb {
  display: flex; align-items: center; gap: 1.6rem; flex-wrap: wrap;
  padding: .6rem 1.1rem;
  background: var(--deep);
  border: 1px solid var(--b0);
  border-radius: 4px; margin-bottom: 1.6rem;
  font-family: var(--fm); font-size: .68rem;
  color: var(--td); letter-spacing: .05em;
}
.lk-sb-item { display: flex; align-items: center; gap: 5px; }
.sok   { color: var(--ok); }
.swarn { color: var(--amber); }
.scyan { color: var(--cyan); }
.lk-sb-right { margin-left: auto; }

/* ── GRADIO CLEANUP ──────────── */
.gradio-container .block,
.gradio-container .form {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}
.gradio-container .gap { gap: 1rem !important; }

/* Labels */
.gradio-container label span,
.gradio-container .block > label > span {
  font-family: var(--fm) !important;
  font-size: .68rem !important;
  color: var(--tm) !important;
  letter-spacing: .1em !important;
  text-transform: uppercase !important;
  margin-bottom: .5rem !important;
  display: block;
}

/* Inputs */
.gradio-container input[type=text],
.gradio-container textarea {
  background: var(--input) !important;
  border: 1px solid var(--b0) !important;
  border-radius: 4px !important;
  color: var(--tp) !important;
  font-family: var(--fm) !important;
  font-size: .8rem !important;
  padding: .8rem 1rem !important;
  caret-color: var(--amber) !important;
  transition: border .18s, box-shadow .18s !important;
  line-height: 1.6 !important;
}
.gradio-container input[type=text]:focus,
.gradio-container textarea:focus {
  border-color: var(--amber) !important;
  box-shadow: 0 0 0 3px var(--ag) !important;
  outline: none !important;
}
.gradio-container input::placeholder,
.gradio-container textarea::placeholder {
  color: var(--td) !important;
  font-style: italic !important;
}

/* Button */
.gradio-container button.lk-btn {
  background: transparent !important;
  border: 1px solid var(--amber) !important;
  color: var(--amber) !important;
  font-family: var(--fm) !important;
  font-size: .78rem !important;
  font-weight: 700 !important;
  letter-spacing: .18em !important;
  text-transform: uppercase !important;
  border-radius: 4px !important;
  padding: .85rem 2rem !important;
  cursor: pointer !important;
  width: 100% !important;
  transition: background .2s, color .2s, box-shadow .2s !important;
}
.gradio-container button.lk-btn:hover {
  background: var(--amber) !important;
  color: #0D1117 !important;
  box-shadow: 0 0 22px var(--ag) !important;
}

/* ── OUTPUT ─────────────────── */
.lk-out-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: .6rem 1.1rem;
  background: var(--deep);
  border: 1px solid var(--b0); border-bottom: none;
  border-radius: 4px 4px 0 0;
  margin-top: 1.6rem;
}
.lk-out-label {
  font-family: var(--fm); font-size: .68rem;
  color: var(--tm); letter-spacing: .12em; text-transform: uppercase;
  display: flex; align-items: center; gap: 8px;
}
.lk-out-label::before { content: '▶'; color: var(--amber); font-size: .6rem; }
.lk-out-tabs {
  font-family: var(--fm); font-size: .62rem;
  color: var(--td); letter-spacing: .08em;
}
.lk-out-tabs b { color: var(--amber); border-bottom: 1px solid var(--amber); padding-bottom: 1px; }

/* Output markdown container */
.lk-out-wrap .prose,
.lk-out-wrap .markdown,
div.lk-console {
  background: var(--panel) !important;
  border: 1px solid var(--b0) !important;
  border-top: 2px solid var(--amber) !important;
  border-radius: 0 0 4px 4px !important;
  padding: 1.6rem 1.8rem !important;
  font-family: var(--fm) !important;
  font-size: .8rem !important;
  color: var(--tp) !important;
  line-height: 1.85 !important;
  min-height: 280px !important;
}
.lk-out-wrap .prose h1,
.lk-out-wrap .prose h2,
.lk-out-wrap .prose h3 {
  font-family: var(--fd) !important;
  letter-spacing: .06em !important;
  color: var(--amber) !important;
  border-bottom: 1px solid var(--b0) !important;
  padding-bottom: .4rem !important;
  margin-bottom: .8rem !important;
}
.lk-out-wrap .prose strong { color: var(--cyan) !important; }
.lk-out-wrap .prose code {
  background: var(--cd) !important;
  border: 1px solid rgba(74,173,204,.15) !important;
  border-radius: 2px !important;
  padding: 1px 6px !important;
  font-family: var(--fm) !important;
  color: var(--cyan) !important;
  font-size: .76rem !important;
}
.lk-out-wrap .prose a {
  color: var(--amber) !important;
  text-decoration: none !important;
  border-bottom: 1px solid var(--ag) !important;
}

/* ── EXAMPLES ───────────────── */
.gradio-container .examples-holder,
.gradio-container table.examples {
  background: var(--deep) !important;
  border: 1px solid var(--b0) !important;
  border-radius: 4px !important;
  margin-top: 2rem !important;
  overflow: hidden !important;
}
.gradio-container .examples-holder td,
.gradio-container table.examples td {
  font-family: var(--fm) !important;
  font-size: .72rem !important;
  color: var(--tm) !important;
  border-color: var(--b0) !important;
  padding: .6rem 1rem !important;
  cursor: pointer !important;
  transition: background .15s !important;
}
.gradio-container .examples-holder tr:hover td,
.gradio-container table.examples tr:hover td {
  background: var(--ad) !important;
  color: var(--tp) !important;
}
.gradio-container .examples-holder th,
.gradio-container table.examples th {
  font-family: var(--fm) !important;
  font-size: .62rem !important;
  color: var(--td) !important;
  letter-spacing: .1em !important;
  text-transform: uppercase !important;
  background: var(--void) !important;
  border-color: var(--b0) !important;
  padding: .5rem 1rem !important;
}

footer, .footer { display: none !important; }

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--void); }
::-webkit-scrollbar-thumb { background: var(--b1); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--amber); }
"""

# ─────────────────────────────────────────────
#  LAYOUT
# ─────────────────────────────────────────────
with gr.Blocks(title="LinkRadar | Belge Keşif Motoru", css=custom_css) as demo:

    # HEADER
    gr.HTML("""
    <div class="lk-header">
      <div class="lk-radar">
        <svg viewBox="0 0 86 86" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <radialGradient id="rg" cx="50%" cy="50%" r="50%">
              <stop offset="0%"   stop-color="#C47A3A" stop-opacity=".1"/>
              <stop offset="100%" stop-color="#C47A3A" stop-opacity="0"/>
            </radialGradient>
          </defs>
          <circle cx="43" cy="43" r="42" class="r-ring"/>
          <circle cx="43" cy="43" r="28" class="r-ring"/>
          <circle cx="43" cy="43" r="15" class="r-ring"/>
          <circle cx="43" cy="43" r="42" class="r-ring-hot"/>
          <line x1="1"  y1="43" x2="85" y2="43" stroke="#1E2D3D" stroke-width=".5"/>
          <line x1="43" y1="1"  x2="43" y2="85" stroke="#1E2D3D" stroke-width=".5"/>
          <circle cx="43" cy="43" r="42" fill="url(#rg)"/>
          <line x1="43" y1="43" x2="43" y2="2" class="r-sweep"/>
          <circle cx="27" cy="20" r="2.4" class="r-dot"/>
          <circle cx="60" cy="52" r="1.7" class="r-dot" style="animation-delay:.9s"/>
          <circle cx="36" cy="63" r="1.3" class="r-dot" style="animation-delay:1.7s"/>
        </svg>
      </div>
      <div class="lk-htxt">
        <div class="lk-badge"><span class="lk-bdot"></span>AGENT SİSTEMİ AKTİF</div>
        <div class="lk-title">LINK<b>RADAR</b></div>
        <div class="lk-sub">
          Web sitelerindeki PDF, Excel ve Word dosyalarını otomatik tespit edip
          içeriklerini özetleyen yapay zeka destekli keşif aracı.
        </div>
      </div>
    </div>
    """)

    # STATUS BAR
    gr.HTML("""
    <div class="lk-sb">
      <div class="lk-sb-item"><span>SYS</span><span class="sok">● HAZIR</span></div>
      <div class="lk-sb-item"><span>AGENTS</span><span class="sok">● 3/3 ONLINE</span></div>
      <div class="lk-sb-item"><span>MODE</span><span class="swarn">ASYNC_STREAM</span></div>
      <div class="lk-sb-item"><span>RUNTIME</span><span class="scyan">LANGGRAPH·v0.2</span></div>
      <div class="lk-sb-right" style="font-family:'Space Mono',monospace;font-size:.62rem;color:#2A3D52;">
        GPT-4o // PROD
      </div>
    </div>
    """)

    # INPUTS
    with gr.Row():
        with gr.Column(scale=5):
            url_input = gr.Textbox(
                label="// HEDEF URL",
                placeholder="https://www.epdk.gov.tr/Detay/Icerik/3-0-104/...",
                lines=1
            )
        with gr.Column(scale=4):
            query_input = gr.Textbox(
                label="// DOĞAL DİL SORGUSU — OPSİYONEL",
                placeholder="2025 yılına ait petrol raporlarını bul",
                lines=1
            )

    submit_btn = gr.Button("▶  TARAMAYI BAŞLAT", elem_classes=["lk-btn"])

    # OUTPUT BAR + PANEL
    gr.HTML("""
    <div class="lk-out-bar">
      <div class="lk-out-label">ANALİZ RAPORU</div>
      <div class="lk-out-tabs"><b>STDOUT</b> &nbsp;|&nbsp; METADATA &nbsp;|&nbsp; LOG</div>
    </div>
    """)

    with gr.Column(elem_classes=["lk-out-wrap"]):
        output_display = gr.Markdown(
            elem_classes=["lk-console"],
            value="<span style='color:#2A3D52;font-family:Space Mono,monospace;font-size:.78rem;'>"
                  "// Sistem bekleme modunda...<br>"
                  "// Hedef URL girin ve taramayı başlatın.</span>"
        )

    submit_btn.click(
        fn=simulate_loading, inputs=[], outputs=[output_display]
    ).then(
        fn=run_analysis_sync, inputs=[url_input, query_input], outputs=[output_display]
    )

    # EXAMPLES
    gr.Examples(
        examples=[
            ["https://www.epdk.gov.tr/Detay/Icerik/3-0-104/aylik-sektor-raporu", "2025 petrol raporları"],
            ["https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Istatistikler/Enflasyon+Verileri/",
             "Enflasyon verileri (excel)"],
        ],
        inputs=[url_input, query_input],
        label="Örnek Vakalar"
    )

    # FOOTER
    gr.HTML("""
    <div style="
      margin-top:3rem; padding-top:1.4rem;
      border-top:1px solid #1E2D3D;
      display:flex; justify-content:space-between; align-items:center;
      font-family:'Space Mono',monospace; font-size:.6rem;
      color:#2A3D52; letter-spacing:.08em;
    ">
      <span>LINKRADAR // AI AGENTIC WORKFLOW CONCEPT</span>
      <span>© 2025 // ALL SYSTEMS NOMINAL</span>
    </div>
    """)


if __name__ == "__main__":
    print("🚀 LinkRadar başlatılıyor...")
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)