"""Gemini yanıt şemaları. Aynı modeller hem JSON şemasını üretir hem yanıtı doğrular."""

from pydantic import BaseModel, ConfigDict, Field


class Axes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sosyallik: int = Field(
        ge=0, le=100, description="0: kendi alanını seven, 100: kalabalıkta canlanan"
    )
    planlilik: int = Field(ge=0, le=100, description="0: akışına bırakan, 100: önceden planlayan")
    stres_yonetimi: int = Field(
        ge=0, le=100, description="0: stresten kolay etkilenen, 100: baskı altında sakin kalan"
    )
    aciklik: int = Field(ge=0, le=100, description="0: alışkın olanı seçen, 100: yeniye açık")


class SingleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tip_adi: str = Field(
        min_length=1, max_length=60, description="Kısa, akılda kalan kişilik tipi adı"
    )
    ozet: str = Field(min_length=1, max_length=900, description="2-4 cümlelik kişisel özet")
    guclu_yonler: list[str] = Field(min_length=3, max_length=5)
    gelisim_alanlari: list[str] = Field(min_length=2, max_length=4)
    eksenler: Axes


class CoupleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uyum_skoru: int = Field(ge=0, le=100)
    ozet: str = Field(min_length=1, max_length=900)
    ortak_yonler: list[str] = Field(min_length=2, max_length=5)
    farklar: list[str] = Field(min_length=1, max_length=5)
    iletisim_onerisi: str = Field(min_length=1, max_length=600)


# Sonuç kartında eksenlerin uç etiketleri (sol: 0, sağ: 100).
AXIS_LABELS: dict[str, tuple[str, str, str]] = {
    "sosyallik": ("Sosyallik", "Kendi alanını seven", "Kalabalıkta canlanan"),
    "planlilik": ("Planlılık", "Akışına bırakan", "Önceden planlayan"),
    "stres_yonetimi": ("Stres yönetimi", "Çabuk etkilenen", "Baskıda sakin"),
    "aciklik": ("Yeniliğe açıklık", "Bildiğini seçen", "Yeniyi arayan"),
}
