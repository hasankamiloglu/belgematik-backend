"""
harici_api.py - Harici (dış) OCR servisi: OCR.space (Hafta 9).

NEDEN HARİCİ API?
    Tesseract bilgisayarda çalışır, ücretsizdir ama kurulum ister ve bazı fişlerde
    zorlanır. OCR.space bulutta çalışan bir OCR servisidir: görseli REST API ile
    gönderiyoruz, metni JSON olarak geri alıyoruz. Ücretsiz paketi var.

NASIL ÇALIŞIR? (REST)
    POST https://api.ocr.space/parse/image
        Başlık (header):  apikey: <ANAHTAR>          -> KİMLİK DOĞRULAMA
        Gövde (form):     file=<görsel>, language=tur, OCREngine=1
    Cevap (JSON):
        {"ParsedResults": [{"ParsedText": "MARKET A.S.\\r\\nTOPLAM 120,00 ..."}],
         "IsErroredOnProcessing": false, "ErrorMessage": null, ...}

GÜVENLİK
    API anahtarı KODA YAZILMAZ. .env dosyasındaki OCR_API_ANAHTARI değişkeninden okunur.
    .env dosyası .gitignore'da olduğu için GitHub'a gitmez. Anahtar loglara ve
    veritabanına da yazılmaz; ekranda sadece maskeli hali gösterilir (K8****1234).

HATA YÖNETİMİ (her hata ApiHatasi olarak fırlatılır, "tur" alanı hatanın türünü söyler)
    anahtar_yok -> .env'de anahtar yok                       -> tekrar denenmez
    kimlik      -> anahtar yanlış (HTTP 401/403)             -> tekrar denenmez
    hiz_siniri  -> çok fazla istek (HTTP 429 / kendi sınırımız) -> tekrar denenmez
    zaman_asimi -> servis zamanında cevap vermedi            -> TEKRAR DENENİR
    baglanti    -> internet yok / servis kapalı              -> TEKRAR DENENİR
    sunucu      -> servisin kendi hatası (HTTP 5xx)          -> TEKRAR DENENİR
    yanit       -> cevap bozuk veya servis işleyemedi        -> tekrar denenmez
    dosya       -> görsel 1 MB sınırının altına indirilemedi -> tekrar denenmez
    Tekrar denemeler arasında 1 sn, sonra 2 sn beklenir (üstel geri çekilme).
"""

import io
import os
import threading
import time
from collections import deque

import requests
from PIL import Image

from app.services.ocr.tesseract import OcrHatasi

MOTOR_ADI = "ocr_space"
API_ADRESI = "https://api.ocr.space/parse/image"

EN_BUYUK_DOSYA = 1024 * 1024  # ücretsiz paketin dosya sınırı: 1 MB
BAGLANTI_SURESI = 5           # saniye: sunucuya BAĞLANMAK için en fazla bekleme
OKUMA_SURESI = 30             # saniye: CEVAP için en fazla bekleme
EN_FAZLA_DENEME = 3           # ilk deneme + 2 tekrar
ILK_BEKLEME = 1.0             # saniye: 1. tekrar öncesi 1 sn, 2. tekrar öncesi 2 sn

# OCR.space kelime bazında güven puanı vermiyor. Denemelerde metni Tesseract'tan
# daha temiz okuduğu için sabit 0.90 kabul ediyoruz (alan güveni = eşleme × bu değer).
API_GUVENI = 0.90

# Bu türlerdeki hatalar geçicidir; biraz bekleyip tekrar denemek işe yarayabilir.
TEKRAR_DENENEBILIR = {"zaman_asimi", "baglanti", "sunucu"}


class ApiHatasi(OcrHatasi):
    """Harici API hatası. OcrHatasi'ndan türediği için eski kod da yakalayabilir."""

    def __init__(self, mesaj, tur, http_kodu=None):
        super().__init__(mesaj)
        self.tur = tur              # hatanın türü (yukarıdaki listeden)
        self.http_kodu = http_kodu  # servisin döndürdüğü HTTP kodu (varsa)
        self.deneme = 1             # kaçıncı denemede vazgeçildi
        self.sure_ms = 0            # toplam geçen süre


# ================================================================ HIZ SINIRI
class HizSinirlayici:
    """
    Kendi tarafımızdaki HIZ SINIRI (rate limit): son 60 saniyede en fazla N çağrı.

    Neden? Ücretsiz paket günde 500 istekle sınırlı. Bir hata veya kötü niyetli
    kullanım yüzünden bu hakkı birkaç dakikada bitirmemek için çağrıları kendimiz
    de sınırlıyoruz. Sınır dolunca API'ye hiç gidilmez.

    Yöntem (kayan pencere): son çağrıların zamanlarını bir kuyrukta tutarız;
    60 saniyeden eski olanları atarız; kalan sayı N'den azsa izin veririz.
    """

    def __init__(self, en_fazla, pencere_sn=60):
        self.en_fazla = en_fazla
        self.pencere_sn = pencere_sn
        self._zamanlar = deque()
        self._kilit = threading.Lock()  # aynı anda iki istek gelirse sayım karışmasın

    def izin_var_mi(self, simdi=None):
        simdi = time.monotonic() if simdi is None else simdi
        with self._kilit:
            while self._zamanlar and simdi - self._zamanlar[0] >= self.pencere_sn:
                self._zamanlar.popleft()       # pencereden çıkan eski çağrılar
            if len(self._zamanlar) >= self.en_fazla:
                return False
            self._zamanlar.append(simdi)
            return True


_sinirlayici = None


def _sinirlayici_al():
    """Dakikalık sınır .env'deki OCR_API_DAKIKA_SINIRI ile değiştirilebilir (varsayılan 10)."""
    global _sinirlayici
    sinir = int(os.getenv("OCR_API_DAKIKA_SINIRI", "10"))
    if _sinirlayici is None or _sinirlayici.en_fazla != sinir:
        _sinirlayici = HizSinirlayici(sinir)
    return _sinirlayici


# ================================================================ ANAHTAR
def _anahtar():
    """API anahtarı sadece ortam değişkeninden (.env) okunur."""
    return os.getenv("OCR_API_ANAHTARI", "").strip()


def anahtar_var_mi():
    return bool(_anahtar())


def maskeli_anahtar():
    """Ekranda göstermek için: 'K81234567890' -> 'K8****7890'. Anahtar yoksa None."""
    a = _anahtar()
    if not a:
        return None
    return a[:2] + "****" + a[-4:] if len(a) > 8 else "****"


# ================================================================ GÖRSEL
def _gorseli_hazirla(gorsel_yolu):
    """
    Görseli JPEG'e çevirip 1 MB sınırının altına indirir.
    Önce kaliteyi düşürür (85 -> 70 -> 55); yetmezse boyutu %25 küçültüp tekrar dener.
    """
    try:
        with Image.open(gorsel_yolu) as acilan:
            gorsel = acilan.convert("L") if acilan.mode not in ("L", "RGB") else acilan.copy()
    except OSError as hata:
        raise ApiHatasi(f"Görsel açılamadı: {hata}", "dosya")

    for _ in range(6):
        for kalite in (85, 70, 55):
            tampon = io.BytesIO()
            gorsel.save(tampon, "JPEG", quality=kalite)
            if tampon.tell() <= EN_BUYUK_DOSYA:
                return tampon.getvalue()
        gorsel = gorsel.resize((max(1, int(gorsel.width * 0.75)), max(1, int(gorsel.height * 0.75))))
    raise ApiHatasi("Görsel 1 MB sınırının altına indirilemedi.", "dosya")


# ================================================================ CEVAP
def _mesajdan_tur(mesaj):
    """Servisin hata mesajından hata türünü tahmin eder (OCR.space hataları gövdede yazar)."""
    m = (mesaj or "").lower()
    if "api key" in m or "apikey" in m:
        return "kimlik"
    if "maximum" in m or "rate limit" in m or "too many" in m:
        return "hiz_siniri"
    if "timed out" in m or "timeout" in m:
        return "zaman_asimi"
    return "yanit"


def yaniti_cozumle(govde):
    """
    Servisin JSON cevabından metni çıkarır (YANIT AYRIŞTIRMA).
    OCR.space hata olsa bile bazen HTTP 200 döndürür; hata bilgisi gövdededir.
    """
    if not isinstance(govde, dict):  # bazen düz metin hata mesajı gelir
        mesaj = str(govde)[:200]
        raise ApiHatasi(f"OCR servisi hata döndürdü: {mesaj}", _mesajdan_tur(mesaj))

    if govde.get("IsErroredOnProcessing"):
        mesajlar = govde.get("ErrorMessage") or []
        if isinstance(mesajlar, str):
            mesajlar = [mesajlar]
        mesaj = " ".join(str(m) for m in mesajlar)[:200] or "bilinmeyen hata"
        raise ApiHatasi(f"OCR servisi belgeyi işleyemedi: {mesaj}", _mesajdan_tur(mesaj))

    sonuclar = govde.get("ParsedResults") or []
    if not sonuclar:
        raise ApiHatasi("OCR servisi boş cevap döndürdü.", "yanit")

    # Çok sayfalı belgede her sayfa ayrı sonuçtur; birleştiriyoruz. \r\n -> \n
    metin = "\n".join(str(s.get("ParsedText") or "") for s in sonuclar)
    return metin.replace("\r\n", "\n").replace("\r", "\n").strip()


def _bir_kez_dene(veri, anahtar, dil, motor):
    """Tek bir HTTP isteği gönderir; sonucu metin olarak veya ApiHatasi olarak döndürür."""
    try:
        cevap = requests.post(
            API_ADRESI,
            headers={"apikey": anahtar},                     # kimlik doğrulama başlıkta
            files={"file": ("belge.jpg", veri, "image/jpeg")},
            data={"language": dil, "OCREngine": motor, "scale": "true",
                  "detectOrientation": "true", "isOverlayRequired": "false",
                  # isTable=true -> metni SATIR SATIR döndür. Olmadan servis fişteki sol
                  # sütunu (TOPLAM) ve sağ sütunu (247,50) ayrı bloklar halinde veriyor,
                  # eşleyici de "TOPLAM" satırında tutarı bulamıyordu. (Hafta 9 düzeltmesi)
                  "isTable": "true"},
            timeout=(BAGLANTI_SURESI, OKUMA_SURESI),          # ZAMAN AŞIMI
        )
    except requests.Timeout:
        raise ApiHatasi("OCR servisi zamanında cevap vermedi (zaman aşımı).", "zaman_asimi")
    except requests.ConnectionError:
        raise ApiHatasi("OCR servisine bağlanılamadı (internet bağlantısı?).", "baglanti")

    kod = cevap.status_code
    if kod in (401, 403):
        raise ApiHatasi("API anahtarı geçersiz veya yetkisiz.", "kimlik", kod)
    if kod == 429:
        raise ApiHatasi("OCR servisinin hız sınırı aşıldı; biraz sonra tekrar deneyin.", "hiz_siniri", kod)
    if kod >= 500:
        raise ApiHatasi(f"OCR servisinde sunucu hatası ({kod}).", "sunucu", kod)
    if kod != 200:
        raise ApiHatasi(f"OCR servisinden beklenmeyen cevap ({kod}).", "yanit", kod)

    try:
        govde = cevap.json()
    except ValueError:
        govde = cevap.text  # JSON değilse düz metin olarak değerlendir
    try:
        return yaniti_cozumle(govde)
    except ApiHatasi as h:
        h.http_kodu = kod
        raise


# ================================================================ ANA FONKSİYON
def metin_oku(gorsel_yolu, bekle=time.sleep):
    """
    Görseldeki yazıyı OCR.space ile okur.

    Döndürür (Tesseract ile AYNI biçim + ek bilgi):
        {"metin", "guven", "motor": "ocr_space", "dil", "deneme", "sure_ms"}
    Hata:
        ApiHatasi (tur alanıyla)

    bekle -> tekrar denemeler arası bekleme fonksiyonu (testlerde beklememek için değiştirilir)
    """
    anahtar = _anahtar()
    if not anahtar:
        raise ApiHatasi("OCR_API_ANAHTARI tanımlı değil (.env dosyasına ekleyin).", "anahtar_yok")
    if not _sinirlayici_al().izin_var_mi():
        raise ApiHatasi("Uygulamanın dakikalık OCR API sınırı doldu; biraz sonra tekrar deneyin.",
                        "hiz_siniri")

    veri = _gorseli_hazirla(gorsel_yolu)
    dil = os.getenv("OCR_API_DIL", "tur")     # OCR.space dil kodu: tur, eng ...
    motor = os.getenv("OCR_API_MOTOR", "1")   # OCR.space motoru: 1 Türkçeyi destekliyor

    baslangic = time.monotonic()
    for deneme in range(1, EN_FAZLA_DENEME + 1):
        try:
            metin = _bir_kez_dene(veri, anahtar, dil, motor)
            return {"metin": metin, "guven": API_GUVENI, "motor": MOTOR_ADI, "dil": dil,
                    "deneme": deneme, "sure_ms": int((time.monotonic() - baslangic) * 1000)}
        except ApiHatasi as h:
            h.deneme = deneme
            h.sure_ms = int((time.monotonic() - baslangic) * 1000)
            if h.tur not in TEKRAR_DENENEBILIR or deneme == EN_FAZLA_DENEME:
                raise
            bekle(ILK_BEKLEME * 2 ** (deneme - 1))  # 1 sn, 2 sn
