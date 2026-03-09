"""
Pydantic Schemas for Structured LLM Output
LLM'den yapılandırılmış yanıt almak için kullanılan şemalar.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class DimensionInfo(BaseModel):
    """Sayfa üzerindeki filtreleme boyutu."""
    name: str = Field(description="Filtreleme boyutunun adı (örn: Yıl, Ay, Kategori)")
    type: str = Field(description="temporal | categorical | geographic | numeric")
    values: list[str] = Field(default_factory=list, description="Tespit edilen değerler")
    is_hierarchical: bool = Field(default=False, description="Hiyerarşik mi?")


class PageAnalysisResult(BaseModel):
    """Web Analyst Agent'ın sayfa analiz çıktısı."""
    institution: str = Field(description="Kurumun resmi adı")
    sector: str = Field(description="Hangi sektöre ait")
    content_type: str = Field(description="Sayfanın içerik türü")
    organization_scheme: str = Field(description="İçeriğin organizasyon mantığı")
    available_dimensions: list[DimensionInfo] = Field(
        default_factory=list,
        description="Mevcut filtreleme boyutları"
    )
    language: str = Field(default="tr", description="Sayfa dili")
    confidence: float = Field(default=0.5, description="Güven skoru (0.0-1.0)")


class FilteredFileInfo(BaseModel):
    """File Scout Agent'ın filtrelenmiş dosya çıktısı."""
    url: str
    filename: str
    extension: str
    file_type: str
    period: str | None = None
    category: str | None = None
    link_text: str = ""


class FileDiscoveryResult(BaseModel):
    """File Scout Agent'ın keşif sonucu."""
    total_found: int = Field(description="Toplam bulunan dosya sayısı")
    after_filter: int = Field(description="Filtre sonrası dosya sayısı")
    filter_interpretation: str = Field(description="Filtrelerin nasıl yorumlandığı")
    filtered_files: list[FilteredFileInfo] = Field(default_factory=list)
    excluded_reasons: list[str] = Field(default_factory=list)


class ContentSummaryResult(BaseModel):
    """Content Analyst Agent'ın dosya özeti."""
    summary: str = Field(description="2-3 cümlelik bilgi-yoğun Türkçe özet")
    key_topics: list[str] = Field(
        default_factory=list,
        description="Ana konular listesi"
    )
    data_type: str = Field(
        default="unknown",
        description="Veri türü: istatistik, finansal, operasyonel, teknik vb."
    )
    coverage_period: str | None = Field(
        default=None,
        description="Kapsam dönemi (varsa)"
    )
    confidence: float = Field(default=0.5, description="Özet güven skoru")
