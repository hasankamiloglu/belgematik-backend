"""
cikarim_servisi.py - Belgeyi işleme akışı ve şema yönetimi (İŞ katmanı, Hafta 7).

BELGE İŞLEME AKIŞI (modüllerin uçtan uca birleştiği yer):

    Hafta 6 ön işlenmiş görsel ──▶ OCR (ocr/motor_secici.py)     -> ham metin + güven
                                   (Hafta 9: önce harici API OCR.space, hata olursa Tesseract)
                                   ──▶ ALAN EŞLEME (extraction/)   -> {alan: değer}
                                       veya YAPAY ZEKÂ (ai/, Hafta 10) -> JSON -> çıktı doğrulama
                                   ──▶ DOĞRULAMA (validation/)     -> geçerli mi + iş kuralları
                                   ──▶ KAYIT (cikarim_repo)        -> cikarim_kayitlari + degerleri
                                                                      belge durumu 'islendi'

İŞ KURALLARI:
    - Sadece belgenin SAHİBİ işleyebilir ve sonucu görebilir.
    - Sadece sistem şemaları veya kullanıcının KENDİ şemaları kullanılabilir.
    - Belge önce ön işlenmiş olmalı (durum 'on_islendi' veya 'islendi').
    - İşleme ek kredi harcamaz (kredi yüklemede düştü); belge farklı şemayla tekrar işlenebilir.
    - Tüm alanlar ve kurallar geçerliyse durum 'dogrulandi', değilse 'bekliyor' (kullanıcı kontrol etmeli).
"""

import json
import os
import re

from psycopg import errors as db_hatalari

from app.data.db import baglanti
from app.data.repositories import cikarim_repo, sema_repo
from app.services import belge_servisi
from app.services.ai import gemini, yapay_zeka_cikarici
from app.services.ai.cikti_dogrulama import DUSUK_GUVEN_ESIGI
from app.services.ai.gemini import YapayZekaHatasi
from app.services.ai.istem import ISTEM_SURUMU
from app.services.extraction.eslestirici import alanlari_esle
from app.services.ocr import motor_secici, tesseract
from app.services.validation.dogrulayici import dogrula

VERI_TIPLERI = ("metin", "tarih", "para", "sayi")
AD_KALIBI = re.compile(r"^[a-z][a-z0-9_]{1,49}$")  # küçük harf, rakam, alt çizgi: toplam_tutar
EN_FAZLA_ALAN = 30


class CikarimHatasi(Exception):
    """Beklenen hatalar. durum_kodu -> HTTP kodu (400, 404, 409, 503)."""

    def __init__(self, mesaj, durum_kodu=400, ayrintilar=None):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.durum_kodu = durum_kodu
        self.ayrintilar = ayrintilar or []


def _iso(deger):
    return deger.isoformat() if hasattr(deger, "isoformat") else deger


def _json_liste(deger):
    """JSONB kolonu bazen liste, bazen metin olarak gelebilir; her durumda liste döndür."""
    return json.loads(deger) if isinstance(deger, str) else (deger or [])


def _sayi(deger):
    """NUMERIC (Decimal) -> float (JSON için)."""
    return float(deger) if deger is not None else None


# ==================================================================== ŞEMALAR
def semalari_listele(kullanici_id):
    """Kullanıcının kullanabileceği şemalar ve alanları."""
    with baglanti() as conn:
        semalar = sema_repo.listele(conn, kullanici_id)
        return [{**s, "alanlar": sema_repo.alanlari_getir(conn, s["id"])} for s in semalar]


def sema_olustur(kullanici_id, veri):
    """
    Kullanıcı kendi şemasını tanımlar (ŞEMA TANIMI).

    Beklenen veri:
        {"ad": "gider_pusulasi", "aciklama": "...",
         "alanlar": [{"alan_adi": "tutar", "veri_tipi": "para", "zorunlu_mu": true,
                      "anahtar_kelimeler": "TUTAR,TOPLAM", "dogrulama_kurali": null}, ...]}
    Bütün hatalar toplanıp birlikte döndürülür (kullanıcı hepsini bir kerede düzeltsin).
    """
    ad = str(veri.get("ad") or "").strip().lower()
    aciklama = str(veri.get("aciklama") or "").strip()[:500] or None
    alanlar = veri.get("alanlar") or []

    hatalar = []
    if not AD_KALIBI.match(ad):
        hatalar.append("Şema adı küçük harf/rakam/alt çizgi olmalı ve harfle başlamalı (ör. gider_pusulasi).")
    if not isinstance(alanlar, list) or not 1 <= len(alanlar) <= EN_FAZLA_ALAN:
        hatalar.append(f"Şemada 1 ile {EN_FAZLA_ALAN} arasında alan olmalı.")
        alanlar = []

    temiz, gorulen = [], set()
    for i, alan in enumerate(alanlar, start=1):
        alan_adi = str(alan.get("alan_adi") or "").strip().lower()
        tip = alan.get("veri_tipi")
        kural = (alan.get("dogrulama_kurali") or "").strip() or None
        if not AD_KALIBI.match(alan_adi):
            hatalar.append(f"{i}. alan: ad geçersiz (ör. fatura_no).")
        elif alan_adi in gorulen:
            hatalar.append(f"{i}. alan: '{alan_adi}' iki kez yazılmış.")
        gorulen.add(alan_adi)
        if tip not in VERI_TIPLERI:
            hatalar.append(f"{i}. alan: veri tipi {', '.join(VERI_TIPLERI)} olmalı.")
        if kural:
            try:
                re.compile(kural)  # regex gerçekten çalışıyor mu?
            except re.error:
                hatalar.append(f"{i}. alan: doğrulama kuralı geçerli bir regex değil.")
        temiz.append({
            "alan_adi": alan_adi, "veri_tipi": tip, "zorunlu_mu": bool(alan.get("zorunlu_mu")),
            "dogrulama_kurali": kural,
            "anahtar_kelimeler": (str(alan.get("anahtar_kelimeler") or "").strip()[:255] or None),
        })
    if hatalar:
        raise CikarimHatasi("Şema bilgileri geçersiz.", 400, hatalar)

    try:
        with baglanti() as conn:
            sema = sema_repo.olustur(conn, kullanici_id, ad, aciklama, temiz)
            return {**sema, "alanlar": sema_repo.alanlari_getir(conn, sema["id"])}
    except db_hatalari.UniqueViolation:
        raise CikarimHatasi(f"'{ad}' adında bir şemanız zaten var.", 409)


def sema_sil(kullanici_id, sema_id):
    """Kullanıcının kendi şemasını siler. Kullanımdaysa (çıkarımda geçiyorsa) silinmez."""
    try:
        with baglanti() as conn:
            silindi = sema_repo.sil(conn, sema_id, kullanici_id)
    except (db_hatalari.RestrictViolation, db_hatalari.ForeignKeyViolation):
        # ON DELETE RESTRICT: geçmiş çıkarımlar bozulmasın diye kullanımdaki şema silinemez.
        # PostgreSQL bu durumda RestrictViolation (kod 23001) hatası verir.
        raise CikarimHatasi("Bu şema işlenmiş belgelerde kullanıldığı için silinemez.", 409)
    if not silindi:
        raise CikarimHatasi("Şema bulunamadı (sistem şemaları silinemez).", 404)


# ================================================================ BELGE İŞLE
YONTEMLER = ("kural", "yapay_zeka")


def belge_isle(kullanici_id, belge_id, sema_id, yukleme_klasoru, yontem="kural"):
    """
    Belgeyi OCR + alan çıkarımı + doğrulamadan geçirip sonucu kaydeder.

    yontem (Hafta 10):
        "kural"      -> Hafta 7'deki kural tabanlı eşleyici (anahtar kelime / kalıp / konum)
        "yapay_zeka" -> Görsel Gemini'ye gönderilir, alanlar JSON olarak alınır ve doğrulanır.
                        Yapay zekâ hata verirse (anahtar yok, kota, bozuk çıktı...) otomatik
                        olarak kural tabanlı eşleyiciye dönülür ve nedeni kaydedilir.
    Döndürür: sonuc() ile aynı biçimde çıkarım sonucu.
    """
    if yontem not in YONTEMLER:
        raise CikarimHatasi("yontem 'kural' veya 'yapay_zeka' olmalı.", 400)

    # 1) Sahiplik + belge uygun mu? (Hafta 6 modülü)
    belge = belge_servisi.getir(kullanici_id, belge_id)  # başkasınınsa 404
    if not belge["on_islenmis"]:
        raise CikarimHatasi(
            "Bu belge için ön işlenmiş görsel yok. PDF'lerin okunması sonraki sürümde eklenecek.", 400
        )

    # 2) Şema: sistem şeması veya kullanıcının kendi şeması olmalı
    with baglanti() as conn:
        sema = sema_repo.kullanilabilir_getir(conn, sema_id, kullanici_id)
        if sema is None:
            raise CikarimHatasi("Şema bulunamadı.", 404)
        alanlar = sema_repo.alanlari_getir(conn, sema_id)

    # 3) OCR: ön işlenmiş görseli oku (Hafta 9: harici API veya Tesseract)
    #    Yapay zekâ yönteminde de OCR yapılır: modelin bulduğu değerler OCR metniyle
    #    KARŞILAŞTIRILIR (uydurma kontrolü). OCR çalışmazsa yapay zekâ yine denenir.
    yol = os.path.join(yukleme_klasoru, belge["islenmis_yol"])
    try:
        ocr = motor_secici.metin_oku(yol, kullanici_id=kullanici_id, belge_id=belge_id)
    except tesseract.OcrHatasi as h:  # harici_api.ApiHatasi da bunun alt sınıfı
        if yontem != "yapay_zeka":
            raise CikarimHatasi(h.mesaj, 503)  # 503 -> hizmet şu an kullanılamıyor
        ocr = {"metin": "", "guven": 1.0, "motor": "yapay_zeka",
               "not": f"OCR yapılamadı ({h.mesaj}); yapay zekâ değerleri OCR ile karşılaştırılamadı."}

    # 4) Alan çıkarımı
    ai = {"yontem": "kural", "model": None, "istem_surumu": None, "ham_cikti": None, "not": None}
    bulunanlar = None
    if yontem == "yapay_zeka":
        try:
            sonuc_ai = yapay_zeka_cikarici.cikar(yol, sema["ad"], alanlar, ocr["metin"] or None,
                                                 kullanici_id=kullanici_id, belge_id=belge_id)
            bulunanlar = sonuc_ai["bulunanlar"]
            ai["yontem"] = "yapay_zeka"
            ai["model"] = sonuc_ai["model"]
            ai["istem_surumu"] = sonuc_ai["istem_surumu"]
            ai["ham_cikti"] = sonuc_ai["ham_cikti"]
            if sonuc_ai["uyarilar"]:
                ai["not"] = " ".join(sonuc_ai["uyarilar"])[:300]
        except YapayZekaHatasi as h:
            # HATALI / BOŞ ÇIKTI YÖNETİMİ: kural tabanlı yönteme dön, nedeni sakla
            if not ocr["metin"]:
                raise CikarimHatasi(f"Yapay zekâ kullanılamadı ({h.mesaj}) ve OCR da yapılamadı.", 503)
            ai["model"] = gemini.model_adi()
            ai["istem_surumu"] = ISTEM_SURUMU
            if h.ham_cikti:  # bozuk çıktıyı da saklıyoruz: neden reddedildiği görülebilsin
                ai["ham_cikti"] = {"hata": h.mesaj, "ham_metin": h.ham_cikti}
            ai["not"] = f"Yapay zekâ kullanılamadı ({h.mesaj}) Kural tabanlı eşleme kullanıldı."

    if bulunanlar is None:
        bulunanlar = alanlari_esle(ocr["metin"], alanlar)
        # Kural tabanlı güven = eşleme yönteminin güveni × OCR'ın okuma güveni
        for b in bulunanlar.values():
            b["guven"] = round(b["guven"] * ocr["guven"], 3)
            b["dusuk_guven"] = b["deger"] is not None and b["guven"] < DUSUK_GUVEN_ESIGI
            b["not"] = None

    # 5) Doğrulama (iki yöntem için de AYNI kurallar)
    alan_sonuclari, kural_sonuclari, hepsi_gecerli = dogrula(alanlar, bulunanlar)

    degerler = [{
        "alan_id": alan["id"],
        "deger": bulunanlar[alan["alan_adi"]]["deger"],
        "guven": bulunanlar[alan["alan_adi"]]["guven"],
        "gecerli_mi": alan_sonuclari[alan["alan_adi"]]["gecerli"],
        "hata_mesaji": alan_sonuclari[alan["alan_adi"]]["hata_mesaji"],
        "dusuk_guven": bulunanlar[alan["alan_adi"]]["dusuk_guven"],
        "kaynak_notu": bulunanlar[alan["alan_adi"]]["not"],
    } for alan in alanlar]

    # 6) Kayıt (tek transaction) -> belge 'islendi'
    #    Düşük güvenli alan varsa kurallar geçse bile kullanıcı kontrol etmeli: 'bekliyor'
    dusuk_var = any(d["dusuk_guven"] for d in degerler)
    durum = "dogrulandi" if hepsi_gecerli and not dusuk_var else "bekliyor"
    with baglanti() as conn:
        cikarim_repo.sonuc_kaydet(conn, belge_id, kullanici_id, sema_id, ocr, durum,
                                  kural_sonuclari, degerler, ai)
    return sonuc(kullanici_id, belge_id)


def sonuc(kullanici_id, belge_id):
    """Belgenin son çıkarım sonucu (alanlar + iş kuralları + ham metin)."""
    belge_servisi.getir(kullanici_id, belge_id)  # sahiplik kontrolü (değilse 404)
    with baglanti() as conn:
        kayit = cikarim_repo.son_cikarim(conn, belge_id, kullanici_id)
        if kayit is None:
            raise CikarimHatasi("Bu belge henüz işlenmedi.", 404)
        alanlar = cikarim_repo.alan_degerleri(conn, kayit["id"])

    return {
        "cikarim_id": kayit["id"],
        "belge_id": kayit["belge_id"],
        "sema": {"id": kayit["sema_id"], "ad": kayit["sema_adi"]},
        "ocr_motoru": kayit["ocr_motoru"],
        "ocr_guveni": _sayi(kayit["guven_skoru"]),
        "ocr_notu": kayit["ocr_notu"],  # Hafta 9: yedek motora geçildiyse nedeni
        # Hafta 10: yöntem ve yapay zekâ bilgileri (şeffaflık)
        "yontem": kayit["cikarim_yontemi"],
        "ai_model": kayit["ai_model"],
        "istem_surumu": kayit["istem_surumu"],
        "ai_notu": kayit["ai_notu"],
        "ai_ham_cikti": kayit["ai_ham_cikti"],
        "durum": kayit["durum"],
        "tarih": _iso(kayit["olusturma_tarihi"]),
        # deger her zaman METİN döner (ör. vergi no "0123..." sayıya çevrilirse baştaki 0 kaybolur)
        "alanlar": [{**a, "deger": None if a["deger"] is None else str(a["deger"]),
                     "guven_skoru": _sayi(a["guven_skoru"])} for a in alanlar],
        "kural_sonuclari": _json_liste(kayit["kural_sonuclari"]),
        "ham_metin": kayit["ham_metin"],
    }
