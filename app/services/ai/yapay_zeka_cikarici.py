"""
yapay_zeka_cikarici.py - Yapay zekâ ile alan çıkarımını uçtan uca yürütür (Hafta 10).

    1) İstem + JSON şeması şemadan üretilir          (istem.py)
    2) Görsel 1 MB altına sıkıştırılıp Gemini'ye gider (gemini.py)
    3) Cevap JSON'a çevrilir ve DOĞRULANIR           (cikti_dogrulama.py)
    4) Çağrı api_cagrilari tablosuna yazılır (başarılı / hata türü)

Hata olursa YapayZekaHatasi fırlatılır; cikarim_servisi bu durumda kural tabanlı
eşleyiciye döner ve kullanıcıya nedenini gösterir.
"""

import logging

from app.data.db import baglanti
from app.data.repositories import api_repo
from app.services.ai import gemini
from app.services.ai.cikti_dogrulama import CiktiHatasi, ciktiyi_dogrula, json_coz
from app.services.ai.gemini import YapayZekaHatasi
from app.services.ai.istem import ISTEM_SURUMU, cevap_semasi, istem_olustur
from app.services.ocr.harici_api import ApiHatasi, _gorseli_hazirla

log = logging.getLogger(__name__)


def _gunluge_yaz(kullanici_id, belge_id, hata=None, cevap=None):
    """Çağrıyı günlüğe yazar; yazılamazsa işlem durmaz."""
    try:
        with baglanti() as conn:
            api_repo.kaydet(
                conn, kullanici_id, belge_id, gemini.SERVIS_ADI,
                "hata" if hata else "basarili",
                hata_turu=hata.tur if hata else None,
                http_kodu=hata.http_kodu if hata else 200,
                deneme_sayisi=hata.deneme if hata else cevap["deneme"],
                sure_ms=hata.sure_ms if hata else cevap["sure_ms"],
                hata_mesaji=hata.mesaj if hata else None,
            )
    except Exception as h:  # noqa: BLE001
        log.warning("Yapay zekâ çağrısı günlüğe yazılamadı: %s", h)


def cikar(gorsel_yolu, sema_adi, alanlar, ocr_metni=None, kullanici_id=None, belge_id=None):
    """
    Döndürür:
        {"bulunanlar": {alan: {...}}, "ham_cikti": {...}, "model": "...",
         "istem_surumu": "v1", "uyarilar": [...]}
    Hata:
        YapayZekaHatasi (tur: anahtar_yok, kimlik, hiz_siniri, zaman_asimi, ..., cikti)
    """
    istem = istem_olustur(sema_adi, alanlar)
    try:
        gorsel = _gorseli_hazirla(gorsel_yolu)
    except ApiHatasi as h:
        raise YapayZekaHatasi(h.mesaj, "dosya")

    try:
        cevap = gemini.uret(istem, gorsel, "image/jpeg", cevap_semasi(alanlar))
    except YapayZekaHatasi as h:
        _gunluge_yaz(kullanici_id, belge_id, hata=h)
        raise

    # ÇIKTI DOĞRULAMA: HTTP başarılı olsa bile çıktı geçersizse bu bir HATADIR
    try:
        ham = json_coz(cevap["metin"])
        bulunanlar, uyarilar = ciktiyi_dogrula(ham, alanlar, ocr_metni)
    except CiktiHatasi as h:
        hata = YapayZekaHatasi(h.mesaj, "cikti", 200, ham_cikti=cevap["metin"][:2000])
        hata.deneme, hata.sure_ms = cevap["deneme"], cevap["sure_ms"]
        _gunluge_yaz(kullanici_id, belge_id, hata=hata)
        raise hata

    _gunluge_yaz(kullanici_id, belge_id, cevap=cevap)
    return {"bulunanlar": bulunanlar, "ham_cikti": ham, "model": cevap["model"],
            "istem_surumu": ISTEM_SURUMU, "uyarilar": uyarilar}
