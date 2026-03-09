# 🔍 LinkRadar — Akıllı Dosya Keşif ve Analiz Sistemi

> Web sayfalarındaki indirilebilir dosyaları otomatik keşfeder, indirir, parse eder ve özetler.

[![Python](https://img.shields.io/badge/Python-3.9+-blue)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-green)](https://langchain-ai.github.io/langgraph/)

## Demo

### 🖥️ Web Arayüzü (UI)  
![LinkRadar Web UI Demo — Agentic Workflow in Action](assets/demo_ui.gif)

### 💻 Terminal (CLI)
![LinkRadar Terminal Demo — Hızlı CLI Entegrasyonu](assets/demo.gif)

## Özellikler

- 🧠 **Doğal Dil Sorgusu** — `"2025 yılına ait petrol raporlarını listele"` gibi Türkçe cümlelerle çalışır
- ⚡ **Paralel İşleme** — `asyncio.gather` + semaphore ile eşzamanlı dosya analizi
- 🔄 **Multi-Strategy Crawl** — Crawl4AI (JS rendering) + httpx fallback
- 🛡️ **Smart Fallback Chain** — Yanlış etiketli dosyaları otomatik algılar ve doğru parser'a yönlendirir
- ✅ **Verifier Feedback Loop** — Sonuçları doğrular, gerekirse yeniden analiz tetikler
- 📊 **Adaptive Parsing** — PDF'in başını, ortasını, sonunu akıllıca örnekler

## Mimari

```
                    ┌──────────────────────────────────┐
                    │         LinkRadar Graph           │
                    └──────────────────────────────────┘

 Doğal Dil       ┌──────────────┐    ┌───────────────┐
 Sorgusu    ───► │ Query Parser │───►│ Web Analyst    │
                 │  (LLM+regex) │    │ (Crawl+LLM)   │
                 └──────────────┘    └───────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  File Scout     │
                                    │ (Deterministic) │
                                    └────────┬────────┘
                                             │
                              ┌──────────────▼──────────────┐
                              │    Content Analyst (PARALEL)  │
                              │  ┌────┐┌────┐┌────┐┌────┐   │
                              │  │ F1 ││ F2 ││ F3 ││ F4 │   │
                              │  └────┘└────┘└────┘└────┘   │
                              └──────────────┬──────────────┘
                                             │
                                    ┌────────▼────────┐
              ┌─── retry ◄─────────│   Verifier      │
              │                    │ (Quality Gate)   │
              │                    └────────┬─────────┘
              │                             │
              ▼                    ┌────────▼────────┐
         File Scout                │ Result Formatter │
                                   └─────────────────┘
```

## Hızlı Başlangıç

```bash
# Kurulum
pip install -r requirements.txt
crawl4ai-setup

# .env ayarla
cp .env.example .env
# OPENAI_API_KEY=your_key_here

# Doğal dil ile çalıştır
python main.py "https://www.epdk.gov.tr/Detay/Icerik/3-0-104/aylik-sektor-raporu" \
  -q "2025 yılına ait petrol sektör raporlarını listele" \
  -o examples/output.json

# Explicit filtreler ile
python main.py "https://www.epdk.gov.tr/..." --year 2025 --month Ocak
```

> **Not:** Başarılı analiz sonuçları ve yapılandırılmış veriler otomatik olarak `examples/` klasörüne JSON formatında kaydedilir.

## 🖥️ Web Arayüzü (Gradio UI)

Terminal (CLI) yerine modern bir web arayüzü üzerinden işlem yapmak isterseniz:

```bash
# Gerekli kütüphanenin yüklü olduğundan emin olun
pip install gradio

# Arayüzü başlatın
python app.py
```

Tarayıcınızda açılacak ekrandan hedef URL'yi ve dilerseniz doğal dil sorgunuzu doğrudan girebilir, sonuçları görsel olarak inceleyebilirsiniz.

## Örnek Çıktı

```
📊 Kaynak: EPDK - Enerji Piyasası Düzenleme Kurumu — Aylık Raporlar
🏛️  Sektör: Enerji
🔍 Filtre: Yıl → 2025

📁 2025 / Ocak
  ├── 📄 2025_Petrol_Piyasası_Ocak_Sektör_Raporu.docx  [631.8 KB]
  │     └── Rafineri üretimi, ithalat ve ihracat verilerini
  │         detaylandıran tablolar içermektedir.
  └── 📄 İl_Bazında_Teslimler_Ocak_2025.xlsx  [267.4 KB]
        └── 81 ilde petrol ürünü teslim verileri...

📁 2025 / Şubat ... Aralık

✅ 16/16 dosya başarıyla analiz edildi (16.3s, paralel)
```

## Proje Yapısı

```
├── main.py                          # CLI giriş noktası (--query, --output)
├── src/
│   ├── agents/
│   │   ├── query_parser.py          # Doğal dil → filtre (LLM + regex)
│   │   ├── web_analyst.py           # Sayfa yapı analizi (LLM)
│   │   ├── file_scout.py            # Deterministik dosya keşfi
│   │   ├── content_analyst.py       # Paralel indirme + parse + özetleme
│   │   └── verifier.py              # Kalite kontrol + feedback loop
│   ├── graph/
│   │   ├── state.py                 # TypedDict state tanımları
│   │   ├── graph_builder.py         # LangGraph StateGraph
│   │   └── routers.py               # Conditional edge routing
│   ├── tools/
│   │   ├── crawl_tool.py            # Multi-strategy crawler
│   │   ├── download_tool.py         # Async file downloader
│   │   └── parsers/                 # Excel, Word, PDF, CSV parsers
│   ├── prompts/                     # LLM system prompts
│   ├── schemas/                     # Pydantic output models
│   └── formatters/                  # Terminal output formatter
├── examples/                        # Örnek JSON çıktılar
├── tests/                           # Unit testler (31 test)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Tasarım Kararları

| Karar | Neden |
|---|---|
| **Paralel `asyncio.gather`** | 16 dosya 16s'de (sequential ~160s olurdu) |
| **Semaphore rate limiting** | API limitlerini ve sunucu yükünü kontrol |
| **Adaptive PDF sampling** | Başlangıç + orta + son sayfalar → tam dosya okumadan yapısal anlayış |
| **Multi-strategy crawl** | Crawl4AI başarısız → httpx+BS4 fallback |
| **Error-message parser fallback** | EPDK gibi siteler dosyayı yanlış etiketliyor, hata mesajından gerçek formatı çıkar |
| **Verifier feedback loop** | Agent'lar arası eleştirel kontrol, düşük başarıda retry |
| **Doğal dil sorgu parser** | Regex hızlı çıkarım + LLM zenginleştirme |

## Teknoloji Seçimleri ve Nedenleri

- **Python 3.9+ & Pydantic v2:** Güçlü tip kontrolü (Type Hinting) ve yapılandırılmış veri doğrulama. (Not: Pydantic v2 runtime syntax çözümü için `eval_type_backport` kullanıldı.)
- **LangGraph:** Döngüsel (Cyclic) yapılar kurabilme yeteneği. Lineer bir akış yerine (A → B → C), `Verifier` ajanının sonuçları beğenmeyip tekrar `Content Analyst`'e gönderebilmesi **Feedback Loop** mimarisini kurmamızı sağladı.
- **Asyncio (AIOHTTP / HTTPX):** I/O temelli bir iş (Web crawling + dosya indirme) olduğu için multi-threading yerine, çok daha hafif ve performanslı olan coroutine/async okuma stratejisi tercih edildi.

## Zorluklar ve Çözümler (EPDK Case Study)

EPDK sitesi gibi kompleks, dinamik ve bazen hatalı yapılandıran sitelere karşı sistemin **Dayanıklılığı (Resilience)** şu şekilde sağlandı:

1. **Yanlış Header / Content-Type Sorunu:**
   - **Sorun:** EPDK sunucusu bazı Excel dosyalarını `.xlsx` yerine `.main+xml` gibi anlamsız header'larla veya uzantısız gönderiyor.
   - **Çözüm:** `Content Analyst` içerisinde bir **Smart Fallback Chain** kuruldu. Sistem `excel_parser`'dan gelen hata mesajını analiz eder ve dosyanın aslında ne olduğunu anlayıp doğru formatta (örn: XML'den çıkararak) tekrar parse eder.

2. **Dinamik JavaScript Linkleri:**
   - **Sorun:** İndirme linkleri her zaman basit bir `<a href="">` tag'i olmuyor, bazen butonların içine gömülü JS fonksiyonları (`javascript:download()`) şeklinde gelebiliyor.
   - **Çözüm:** **Crawl4AI** tercih edildi. Puppeteer mantığıyla arkada sayfayı render eder ve dinamik linkleri de DOM üzerinden toplayabilir. Performans sorunu olursa otomatik olarak `httpx + BeautifulSoup` yöntemine geri çekilir (Multi-strategy crawl).

3. **Uzun PDF / Word Dosyaları ve LLM Maliyeti:**
   - **Sorun:** 200 sayfalık bir piyasa raporunun tamamını LLM'e göndermek hem token limitlerine çarpar hem de yavaştır.
   - **Çözüm:** **Adaptive Sampling** geliştirildi. PDF'in ilk 3 sayfası (genel özet/içindekiler), ortasından 2 sayfa (veri yapısı) ve son sayfası örneklenerek (sampling) modele verilir. Böylece dosyanın bütünü okunmadan ne hakkında olduğu yüksek doğrulukla özetlenir.

### 🎯 Desteklenen & Test Edilen Kaynaklar
Bu yapı oldukça esnektir ve farklı kurum sitelerindeki testlerden başarıyla geçmiştir:
- **EPDK (Enerji Piyasası Düzenleme Kurumu):** Dinamik JS render, hatalı içerik tanımlayıcılarına (header mismatch) sahip linklere karşı doğrulama testi (Case study gereksinimi).
- **TCMB (Türkiye Cumhuriyet Merkez Bankası):** Parçalanmış ve derin arşiv dizinlerinde yer alan kompleks enflasyon / istatistik verilerinin ayrıştırılması.
- **KAP (Kamuyu Aydınlatma Platformu):** Şirket bildirimlerinde (PDF/Word ağırlıklı) sayfa başlıkları ve konuların hızlıca özetlenmesi senaryoları.

## Docker

```bash
docker-compose up
# veya
docker build -t linkradar .
docker run --env-file .env linkradar "https://site.com" -q "2025 raporları"
```

## Test

```bash
pytest tests/ -v
# 31/31 ✅
```
