"""
cikti_dogrulama.py - Yapay zekâ çıktısını DOĞRULAMA (Hafta 10).

Yapay zekânın cevabı "doğru" kabul edilmez; şu kontrollerden geçer:

    1) JSON MU?         Model bazen ```json ... ``` içinde veya bozuk JSON döndürebilir.
                        Kod bloğu işaretleri temizlenir; yine çözülemezse -> CiktiHatasi.
    2) YAPI DOĞRU MU?   {"alanlar": {...}} olmalı. Şemada olmayan alanlar ATILIR,
                        eksik alanlar "bulunamadı" sayılır.
    3) TİPLER DOĞRU MU? deger metin/sayı/null olmalı; guven 0-1 arasında sayı olmalı
                        (değilse 0.5 kabul edilir ve not düşülür).
    4) BİÇİM            Değer, alanın veri tipine göre bizim biçimimize çevrilir:
                        para "1.234,50 TL" -> "1234.50", tarih "12.10.2026" -> "2026-10-12".
                        Çevrilemiyorsa değer reddedilir (None).
    5) KANIT (OCR)      Değer, OCR'ın okuduğu metinde GERÇEKTEN geçiyor mu?
                        Geçmiyorsa model "uydurmuş" (halüsinasyon) olabilir -> güven yarıya iner.
    6) DÜŞÜK GÜVEN      Son güven DUSUK_GUVEN_ESIGI'nin (0.40) altındaysa VEYA değer OCR
                        metninde bulunamadıysa alan işaretlenir; kullanıcı kontrol etmeden
                        belge "doğrulandı" sayılmaz.

Sonrasında alanlar Hafta 7'deki AYNI doğrulama kurallarından da geçer
(zorunlu alan, VKN kontrol hanesi, KDV hesabı, Matrah + KDV = Toplam).
"""

import json
import re

from app.services.extraction.metin_araclari import (
    kdv_oranlari_bul,
    para_bul,
    para_coz,
    sadelestir,
    tarih_bul,
    tarih_coz,
)

DUSUK_GUVEN_ESIGI = 0.40   # bunun altındaki alanlar "kontrol edin" diye işaretlenir
KANITSIZ_CARPAN = 0.5      # değer OCR metninde yoksa güven bununla çarpılır
VARSAYILAN_GUVEN = 0.5     # model geçersiz güven verirse


class CiktiHatasi(Exception):
    def __init__(self, mesaj):
        super().__init__(mesaj)
        self.mesaj = mesaj


# ============================================================ 1) JSON
def json_coz(metin):
    """Modelin metnini JSON'a çevirir. ```json ... ``` işaretlerini temizler."""
    temiz = (metin or "").strip()
    temiz = re.sub(r"^```(?:json)?\s*|\s*```$", "", temiz, flags=re.IGNORECASE).strip()
    if not temiz:
        raise CiktiHatasi("Yapay zekâ boş çıktı döndürdü.")
    try:
        return json.loads(temiz)
    except json.JSONDecodeError as h:
        raise CiktiHatasi(f"Yapay zekâ çıktısı geçerli JSON değil ({h.msg}).")


# ============================================================ 4) BİÇİM
def _bicimle(alan, deger):
    """Değeri veri tipine göre sistem biçimine çevirir. Çevrilemezse (None, neden)."""
    if deger is None:
        return None, None
    metin = str(deger).strip()
    if metin == "" or metin.lower() in ("null", "none", "yok", "-"):
        return None, None

    tip, ad = alan["veri_tipi"], alan["alan_adi"]
    if tip == "para":
        tutar = para_coz(metin.replace(" ", ""))
        if tutar is None:
            # Model "1234.50" yazdıysa para_coz zaten çözer; "1234.5" gibi tek haneli kuruş:
            tek = re.fullmatch(r"(\d+)\.(\d)", metin)
            tutar = para_coz(f"{tek.group(1)},{tek.group(2)}0") if tek else None
        return (f"{tutar:.2f}", None) if tutar is not None else (None, "Para biçimi anlaşılamadı.")
    if tip == "tarih":
        tarih = tarih_coz(metin)
        return (tarih.isoformat(), None) if tarih else (None, "Tarih biçimi anlaşılamadı.")
    if tip == "sayi":
        if ad == "kdv_orani":
            metin = re.sub(r"[.,]0+$", "", metin.replace(" ", ""))  # "20.0" -> "20"
            oranlar = kdv_oranlari_bul(metin if "%" in metin else f"%{metin}")
            return (str(oranlar[0]), None) if oranlar else (None, "KDV oranı anlaşılamadı.")
        rakam = re.fullmatch(r"-?\d+(?:[.,]\d+)?", metin)
        return (metin.replace(",", "."), None) if rakam else (None, "Sayı biçimi anlaşılamadı.")
    # metin
    if ad in ("vergi_no", "tckn", "fis_no", "fatura_no") or ad.endswith("_no"):
        rakamlar = re.sub(r"\D", "", metin)
        if rakamlar and len(rakamlar) >= len(re.sub(r"\s", "", metin)) * 0.6:
            return rakamlar, None  # "VKN: 123 456 7808" -> "1234567808"
    return metin[:255], None


# ============================================================ 5) KANIT
def ocr_metninde_var_mi(alan, deger, ocr_metni):
    """
    Değer OCR metninde geçiyor mu? (Yapay zekâ uydurmuş mu kontrolü)
    Karşılaştırma tipe göre yapılır: "247.50" ile fişteki "*247,50" aynı kabul edilir.
    """
    if not ocr_metni or deger is None:
        return None  # kontrol yapılamadı
    tip = alan["veri_tipi"]
    satirlar = ocr_metni.splitlines()

    if tip == "para":
        hedef = para_coz(deger)
        return any(hedef in para_bul(s) for s in satirlar)
    if tip == "tarih":
        hedef = tarih_coz(deger)
        return any(tarih_bul(s) == hedef for s in satirlar)

    sade_ocr = sadelestir(ocr_metni)
    if tip == "sayi" or re.fullmatch(r"\d+", str(deger)):
        if alan["alan_adi"] == "kdv_orani":
            return int(float(deger)) in kdv_oranlari_bul(sade_ocr)
        return str(deger) in re.sub(r"\D", "", sade_ocr) if len(str(deger)) >= 4 \
            else re.search(rf"(?<!\d){re.escape(str(deger))}(?!\d)", sade_ocr) is not None

    # metin: kelimelerin en az %60'ı OCR metninde geçmeli (OCR küçük hatalar yapabilir)
    kelimeler = [k for k in re.findall(r"\w+", sadelestir(deger)) if len(k) > 1]
    if not kelimeler:
        return None
    gecen = sum(1 for k in kelimeler if k in sade_ocr)
    return gecen / len(kelimeler) >= 0.6


# ============================================================ ANA FONKSİYON
def _guven(ham):
    """Güveni 0-1 arası sayıya çevirir. Geçersizse (None, not)."""
    try:
        guven = float(ham)
    except (TypeError, ValueError):
        return None
    if guven != guven:  # NaN
        return None
    if 1 < guven <= 100:  # model yüzde vermiş olabilir: 95 -> 0.95
        guven /= 100
    return min(max(guven, 0.0), 1.0)


def ciktiyi_dogrula(ham, alanlar, ocr_metni=None):
    """
    Modelin JSON'unu doğrular ve eşleyiciyle AYNI biçimde sonuç döndürür.

    Döndürür:
        bulunanlar -> {alan_adi: {"deger", "guven", "yontem", "dusuk_guven", "not"}}
        uyarilar   -> ["Şemada olmayan alan yok sayıldı: ...", ...]
    Hata:
        CiktiHatasi -> yapı tamamen bozuksa (kural tabanlı yönteme dönülür)
    """
    if not isinstance(ham, dict) or not isinstance(ham.get("alanlar"), dict):
        raise CiktiHatasi('Yapay zekâ çıktısı beklenen yapıda değil ({"alanlar": {...}} olmalı).')

    gelen = ham["alanlar"]
    sema_adlari = {a["alan_adi"] for a in alanlar}
    uyarilar = [f"Şemada olmayan alan yok sayıldı: {ad}" for ad in gelen if ad not in sema_adlari]

    bulunanlar = {}
    for alan in alanlar:
        ad = alan["alan_adi"]
        kayit = gelen.get(ad)
        notlar = []

        if kayit is None:
            kayit = {"deger": None, "guven": 0}
            notlar.append("Yapay zekâ bu alanı döndürmedi.")
        elif not isinstance(kayit, dict):  # {"toplam_tutar": "247.50"} gibi düz değer
            kayit = {"deger": kayit, "guven": VARSAYILAN_GUVEN}
            notlar.append("Güven bilgisi yoktu; 0.5 kabul edildi.")

        kanit = None
        ham_deger = kayit.get("deger")
        if isinstance(ham_deger, (dict, list, bool)):
            ham_deger = None
            notlar.append("Değer tipi geçersizdi.")

        guven = _guven(kayit.get("guven"))
        if guven is None:
            guven = VARSAYILAN_GUVEN
            notlar.append("Güven değeri geçersizdi; 0.5 kabul edildi.")

        deger, neden = _bicimle(alan, ham_deger)
        if neden:
            notlar.append(f"{neden} (yapay zekâ: '{str(ham_deger)[:40]}')")
        if deger is None:
            guven = 0.0
        else:
            kanit = ocr_metninde_var_mi(alan, deger, ocr_metni)
            if kanit is False:
                guven *= KANITSIZ_CARPAN
                notlar.append("Değer OCR metninde doğrulanamadı (yapay zekâ uydurmuş olabilir).")

        guven = round(guven, 3)
        bulunanlar[ad] = {
            "deger": deger,
            "guven": guven,
            "yontem": "yapay_zeka",
            "dusuk_guven": deger is not None and (guven < DUSUK_GUVEN_ESIGI or kanit is False),
            "not": " ".join(notlar)[:255] or None,
        }
    return bulunanlar, uyarilar
