"""
motor_secici.py - Hangi OCR motorunun kullanılacağına karar verir (Hafta 9).

    .env -> OCR_MOTORU=otomatik | api | tesseract

    otomatik  (varsayılan) -> Anahtar varsa önce harici API (OCR.space) denenir.
                              API hata verirse YEDEK olarak Tesseract kullanılır.
                              Anahtar yoksa doğrudan Tesseract.
    api                    -> Sadece harici API. Hata olursa kullanıcıya hata döner.
    tesseract              -> Sadece bilgisayardaki Tesseract (Hafta 7 davranışı).

Her API çağrısı (başarılı veya hatalı) api_cagrilari tablosuna yazılır.
Günlük yazılamazsa (ör. veritabanı geçici sorun) belge işleme DURMAZ; sadece uyarı loglanır.

İki motor da aynı biçimde sonuç döndürür: {"metin", "guven", "motor", ...}
Bu sayede cikarim_servisi motorun hangisi olduğunu bilmek zorunda değildir.
"""

import logging
import os

from app.data.db import baglanti
from app.data.repositories import api_repo
from app.services.ocr import harici_api, tesseract

MOTORLAR = ("otomatik", "api", "tesseract")
log = logging.getLogger(__name__)


def secili_motor():
    motor = os.getenv("OCR_MOTORU", "otomatik").strip().lower()
    return motor if motor in MOTORLAR else "otomatik"


def _gunluge_yaz(kullanici_id, belge_id, durum, hata=None, sonuc=None):
    """API çağrısını günlüğe yazar. Hata olsa bile asıl işlemi bozmaz."""
    try:
        with baglanti() as conn:
            api_repo.kaydet(
                conn, kullanici_id, belge_id, harici_api.MOTOR_ADI, durum,
                hata_turu=hata.tur if hata else None,
                http_kodu=hata.http_kodu if hata else 200,
                deneme_sayisi=(hata.deneme if hata else sonuc["deneme"]),
                sure_ms=(hata.sure_ms if hata else sonuc["sure_ms"]),
                hata_mesaji=hata.mesaj if hata else None,
            )
    except Exception as h:  # noqa: BLE001 - günlük yazılamadı diye belge işleme durmasın
        log.warning("API çağrısı günlüğe yazılamadı: %s", h)


def metin_oku(gorsel_yolu, kullanici_id=None, belge_id=None):
    """
    Seçili motora göre görseli okur.
    Döndürür: {"metin", "guven", "motor", "not"}  (not -> yedeğe geçildiyse nedeni, yoksa None)
    Hata: tesseract.OcrHatasi (ApiHatasi da bunun alt sınıfıdır)
    """
    motor = secili_motor()

    if motor == "tesseract" or (motor == "otomatik" and not harici_api.anahtar_var_mi()):
        return {**tesseract.metin_oku(gorsel_yolu), "not": None}

    try:
        sonuc = harici_api.metin_oku(gorsel_yolu)
    except harici_api.ApiHatasi as hata:
        _gunluge_yaz(kullanici_id, belge_id, "hata", hata=hata)
        if motor == "api":
            raise  # yedek motor istenmedi: hatayı kullanıcıya bildir
        # YEDEK: API çalışmadı -> Tesseract ile oku (Tesseract da yoksa OcrHatasi fırlar)
        yedek = tesseract.metin_oku(gorsel_yolu)
        return {**yedek, "not": f"Harici OCR kullanılamadı ({hata.mesaj}) Tesseract ile okundu."}

    _gunluge_yaz(kullanici_id, belge_id, "basarili", sonuc=sonuc)
    return {**sonuc, "not": None}


def durum_bilgisi():
    """Yönetici paneli için: hangi motor seçili, anahtar tanımlı mı (maskeli), sınırlar."""
    from app.services.ai import gemini  # Hafta 10: yapay zekâ servisinin durumu da gösterilir

    return {
        "yapay_zeka": {"servis": gemini.SERVIS_ADI, "model": gemini.model_adi(),
                       "anahtar": gemini.maskeli_anahtar(),
                       "dakika_siniri": int(os.getenv("AI_DAKIKA_SINIRI", "8"))},
        "secili_motor": secili_motor(),
        "servis": harici_api.MOTOR_ADI,
        "anahtar": harici_api.maskeli_anahtar(),  # gerçek anahtar ASLA döndürülmez
        "dakika_siniri": int(os.getenv("OCR_API_DAKIKA_SINIRI", "10")),
        "tesseract_kurulu": tesseract.kurulu_mu(),
    }


def cagri_ozeti(limit=30):
    """Yönetici paneli: motor durumu + son 24 saat özeti + son çağrılar."""
    with baglanti() as conn:
        ozet = api_repo.son_24_saat_ozeti(conn)
        cagrilar = api_repo.son_cagrilar(conn, limit)
    return {
        **durum_bilgisi(),
        "son_24_saat": {k: int(v) for k, v in dict(ozet).items()},
        "cagrilar": [{**c, "tarih": c["tarih"].isoformat() if hasattr(c["tarih"], "isoformat")
                      else c["tarih"]} for c in cagrilar],
    }
