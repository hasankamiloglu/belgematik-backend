"""
gemini.py - Google Gemini API istemcisi (Hafta 10).

Gemini, Google'ın büyük dil modeli (LLM). Görseli de "görebilir" (çok kipli / multimodal).
Ücretsiz anahtar: https://aistudio.google.com/apikey

İSTEK (REST):
    POST https://generativelanguage.googleapis.com/v1beta/models/<MODEL>:generateContent
    Başlık:  x-goog-api-key: <ANAHTAR>
    Gövde:   {"contents": [{"parts": [{"text": İSTEM}, {"inline_data": {görsel, base64}}]}],
              "generationConfig": {"temperature": 0,
                                   "responseMimeType": "application/json",
                                   "responseSchema": ŞEMA}}
    temperature 0 -> model her seferinde aynı girdiye mümkün olduğunca aynı cevabı verir
                     (yaratıcılık değil, tutarlılık istiyoruz).
CEVAP:
    {"candidates": [{"content": {"parts": [{"text": "{\\"alanlar\\": ...}"}]},
                     "finishReason": "STOP"}],
     "usageMetadata": {"totalTokenCount": 1234}}

HATALAR (YapayZekaHatasi.tur):
    anahtar_yok, kimlik (anahtar yanlış), hiz_siniri (429), zaman_asimi, baglanti,
    sunucu (5xx), yanit (istek/model hatası), guvenlik (güvenlik filtresi engelledi),
    cikti (cevap boş veya yarım)
    Geçici olanlar (zaman_asimi, baglanti, sunucu) 1 sn / 2 sn bekleyip tekrar denenir.

API anahtarı .env -> AI_API_ANAHTARI. Koda, depoya, loglara yazılmaz.
"""

import base64
import os
import time

import requests

from app.services.ocr.harici_api import HizSinirlayici

SERVIS_ADI = "gemini"
API_KOKU = "https://generativelanguage.googleapis.com/v1beta/models"
# Denemede (27.11.2026) "gemini-flash-latest" ve "gemini-2.5-flash" bu anahtarla cevap vermedi
# (zaman aşımı / 404); "gemini-3-flash-preview" 2 saniyede cevap verdi. .env -> AI_MODEL ile değişir.
VARSAYILAN_MODEL = "gemini-3-flash-preview"

BAGLANTI_SURESI = 5    # saniye
OKUMA_SURESI = 60      # saniye: dil modeli OCR'dan yavaş cevap verir
EN_FAZLA_DENEME = 3
ILK_BEKLEME = 1.0
TEKRAR_DENENEBILIR = {"zaman_asimi", "baglanti", "sunucu"}


class YapayZekaHatasi(Exception):
    def __init__(self, mesaj, tur, http_kodu=None, ham_cikti=None):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.tur = tur
        self.http_kodu = http_kodu
        self.ham_cikti = ham_cikti  # çıktı hatasında modelin döndürdüğü metin (şeffaflık için)
        self.deneme = 1
        self.sure_ms = 0


def _anahtar():
    return os.getenv("AI_API_ANAHTARI", "").strip()


def anahtar_var_mi():
    return bool(_anahtar())


def maskeli_anahtar():
    a = _anahtar()
    if not a:
        return None
    return a[:4] + "****" + a[-4:] if len(a) > 10 else "****"


def model_adi():
    return os.getenv("AI_MODEL", VARSAYILAN_MODEL).strip() or VARSAYILAN_MODEL


_sinirlayici = None


def _sinirlayici_al():
    """Kendi hız sınırımız: dakikada en fazla AI_DAKIKA_SINIRI çağrı (varsayılan 8)."""
    global _sinirlayici
    sinir = int(os.getenv("AI_DAKIKA_SINIRI", "8"))
    if _sinirlayici is None or _sinirlayici.en_fazla != sinir:
        _sinirlayici = HizSinirlayici(sinir)
    return _sinirlayici


def _hata_govdesi(cevap):
    """Google'ın hata cevabından mesajı çıkarır: {"error": {"message": "...", "status": "..."}}"""
    try:
        hata = cevap.json().get("error", {})
        return f'{hata.get("status", "")} {hata.get("message", "")}'.strip()[:200]
    except (ValueError, AttributeError):
        return (cevap.text or "")[:200]


def cevabi_coz(govde):
    """
    Gemini cevabından modelin yazdığı metni çıkarır.
    Model cevap vermediyse NEDENİNİ bulup uygun hatayı fırlatır.
    """
    if not isinstance(govde, dict):
        raise YapayZekaHatasi("Yapay zekâ servisi anlaşılmayan bir cevap döndürdü.", "yanit")

    engel = (govde.get("promptFeedback") or {}).get("blockReason")
    if engel:
        raise YapayZekaHatasi(f"Yapay zekâ güvenlik filtresi isteği engelledi ({engel}).", "guvenlik")

    adaylar = govde.get("candidates") or []
    if not adaylar:
        raise YapayZekaHatasi("Yapay zekâ boş cevap döndürdü.", "cikti")

    aday = adaylar[0]
    bitis = aday.get("finishReason")
    parcalar = (aday.get("content") or {}).get("parts") or []
    metin = "".join(p.get("text", "") for p in parcalar if isinstance(p, dict)).strip()

    if bitis in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
        raise YapayZekaHatasi(f"Yapay zekâ güvenlik nedeniyle cevabı kesti ({bitis}).", "guvenlik")
    if bitis == "MAX_TOKENS":
        raise YapayZekaHatasi("Yapay zekânın cevabı yarım kaldı (uzunluk sınırı).", "cikti", ham_cikti=metin)
    if not metin:
        raise YapayZekaHatasi("Yapay zekâ boş cevap döndürdü.", "cikti")
    return metin


def _bir_kez_dene(model, anahtar, govde):
    try:
        cevap = requests.post(
            f"{API_KOKU}/{model}:generateContent",
            headers={"x-goog-api-key": anahtar, "Content-Type": "application/json"},
            json=govde,
            timeout=(BAGLANTI_SURESI, OKUMA_SURESI),
        )
    except requests.ConnectTimeout:
        raise YapayZekaHatasi("Yapay zekâ servisine bağlanılamadı (bağlantı zaman aşımı).", "zaman_asimi")
    except requests.Timeout:  # bağlandı ama cevap gelmedi (ReadTimeout)
        raise YapayZekaHatasi(f"Yapay zekâ {OKUMA_SURESI} sn içinde cevap vermedi (zaman aşımı). "
                              "Model yoğun olabilir; .env'de AI_MODEL değiştirmeyi deneyin.", "zaman_asimi")
    except requests.ConnectionError:
        raise YapayZekaHatasi("Yapay zekâ servisine bağlanılamadı (internet bağlantısı?).", "baglanti")

    kod = cevap.status_code
    if kod == 200:
        try:
            return cevabi_coz(cevap.json())
        except ValueError:
            raise YapayZekaHatasi("Yapay zekâ servisi JSON olmayan bir cevap döndürdü.", "yanit", kod)

    ayrinti = _hata_govdesi(cevap)
    if kod in (401, 403) or "API_KEY_INVALID" in ayrinti or "API key not valid" in ayrinti:
        raise YapayZekaHatasi("Yapay zekâ API anahtarı geçersiz veya yetkisiz.", "kimlik", kod)
    if kod == 429:
        raise YapayZekaHatasi("Yapay zekâ servisinin kotası/hız sınırı doldu; biraz sonra deneyin.",
                              "hiz_siniri", kod)
    if kod == 404:
        raise YapayZekaHatasi(f"Model bulunamadı: '{model}'. .env'deki AI_MODEL değerini kontrol edin.",
                              "yanit", kod)
    if kod >= 500:
        raise YapayZekaHatasi(f"Yapay zekâ servisinde sunucu hatası ({kod}).", "sunucu", kod)
    raise YapayZekaHatasi(f"Yapay zekâ isteği reddedildi ({kod}): {ayrinti}", "yanit", kod)


def uret(istem, gorsel, mime_turu, cevap_semasi, bekle=time.sleep):
    """
    Görsel + istem gönderir, modelin JSON METNİNİ döndürür (henüz doğrulanmamış!).

    Döndürür: {"metin": "...", "model": "...", "deneme": 1, "sure_ms": 1234}
    Hata:     YapayZekaHatasi
    """
    anahtar = _anahtar()
    if not anahtar:
        raise YapayZekaHatasi("AI_API_ANAHTARI tanımlı değil (.env dosyasına ekleyin).", "anahtar_yok")
    if not _sinirlayici_al().izin_var_mi():
        raise YapayZekaHatasi("Uygulamanın dakikalık yapay zekâ sınırı doldu; biraz sonra deneyin.",
                              "hiz_siniri")

    model = model_adi()
    govde = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": istem},
                {"inline_data": {"mime_type": mime_turu,
                                 "data": base64.b64encode(gorsel).decode("ascii")}},
            ],
        }],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": cevap_semasi,
        },
    }

    baslangic = time.monotonic()
    for deneme in range(1, EN_FAZLA_DENEME + 1):
        try:
            metin = _bir_kez_dene(model, anahtar, govde)
            return {"metin": metin, "model": model, "deneme": deneme,
                    "sure_ms": int((time.monotonic() - baslangic) * 1000)}
        except YapayZekaHatasi as h:
            h.deneme = deneme
            h.sure_ms = int((time.monotonic() - baslangic) * 1000)
            if h.tur not in TEKRAR_DENENEBILIR or deneme == EN_FAZLA_DENEME:
                raise
            bekle(ILK_BEKLEME * 2 ** (deneme - 1))


def modelleri_listele():
    """manage.py ai-kontrol için: anahtarla kullanılabilen ve generateContent destekleyen modeller."""
    cevap = requests.get(API_KOKU, headers={"x-goog-api-key": _anahtar()},
                         timeout=(BAGLANTI_SURESI, 20))
    cevap.raise_for_status()
    return [m["name"].split("/")[-1] for m in cevap.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])]
