"""
goruntu.py - Görsel doğrulama, kalite ölçümü ve ön işleme.

Kütüphane: Pillow (pip install Pillow  ->  from PIL import Image)

AKIŞ:
    1) gorsel_ac()     -> Dosya gerçekten PNG/JPEG mi? Bozuk mu? Çok mu küçük?
    2) kalite_olc()    -> Bulanık mı? Karanlık mı? Kontrast düşük mü? (0-100 puan)
    3) on_isle()       -> Döndür, griye çevir, küçült, kontrast aç, keskinleştir
    4) kucuk_resim()   -> Listede gösterilecek önizleme

Düşük kaliteli görsele iki tür tepki veriyoruz:
    KESİN RED  (GorselHatasi)  -> bozuk dosya, sahte uzantı, çok küçük çözünürlük,
                                  aşırı büyük piksel sayısı, puanı çok düşük görsel
    UYARI      (listeye eklenir)-> bulanık, karanlık/parlak, düşük kontrast
                                  Belge kaydedilir ama kullanıcı uyarılır.
"""

import io

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

# ------------------------------------------------------------------ KURALLAR
# Kısa kenar bundan küçükse yazılar okunamaz -> RED
EN_KUCUK_KENAR = 400
# Uzun kenar bundan büyükse küçültülür (OCR için yeterli, disk ve hız kazanılır)
EN_BUYUK_KENAR = 2000
# Toplam piksel sınırı: 40 milyon (ör. 8000x5000). "Sıkıştırma bombası" denilen,
# küçük dosya ama devasa görsel saldırısına karşı Pillow'un kendi korumasını da açıyoruz.
EN_FAZLA_PIKSEL = 40_000_000
Image.MAX_IMAGE_PIXELS = EN_FAZLA_PIKSEL

# Kalite eşikleri (örnek fiş görselleriyle denenerek belirlendi, bkz. tests/test_on_isleme.py)
BULANIK_ESIGI = 100      # keskinlik bunun altındaysa "bulanık"           -> uyarı
COK_BULANIK_ESIGI = 20   # bunun altındaysa yazılar okunamaz              -> red
KARANLIK_ESIGI = 60      # ortalama parlaklık (0-255) bunun altındaysa    -> uyarı
PATLAMA_ORANI = 0.40     # piksellerin %40'tan fazlası tam beyazsa (flaş)  -> uyarı
KONTRAST_ESIGI = 100     # en koyu ile en açık ton arası farkı bundan azsa -> uyarı
EN_DUSUK_PUAN = 40       # puan bunun altındaysa görsel kaydedilmez        -> red

# Uzantı -> Pillow'un dosyanın İÇİNDEN okuduğu gerçek biçim
UZANTI_BICIM = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG"}


class GorselHatasi(Exception):
    """Görsel kesin olarak reddedildiğinde fırlatılır. mesaj kullanıcıya gösterilir."""

    def __init__(self, mesaj):
        super().__init__(mesaj)
        self.mesaj = mesaj


# ---------------------------------------------------------------- 1) AÇ / DOĞRULA
def gorsel_ac(veri, uzanti):
    """
    Baytları görsel olarak açar ve temel kuralları kontrol eder.

    Parametreler:
        veri   -> dosyanın baytları (bytes)
        uzanti -> dosya adındaki uzantı: "png", "jpg" veya "jpeg"
    Döndürür:
        Pillow Image nesnesi (EXIF'e göre doğru yöne çevrilmiş)
    Hata:
        GorselHatasi -> dosya bozuk, uzantısı yalan, çok küçük veya çok büyükse
    """
    try:
        # verify() -> dosyayı çözmeden yapısını kontrol eder (bozuk mu?)
        Image.open(io.BytesIO(veri)).verify()
        # verify() sonrası nesne kullanılamaz; bu yüzden yeniden açıyoruz
        gorsel = Image.open(io.BytesIO(veri))
        gorsel.load()  # baytları gerçekten çöz (bozuk JPEG burada yakalanır)
    except Image.DecompressionBombError:
        raise GorselHatasi("Görsel çok büyük (piksel sayısı sınırı aşıldı).")
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise GorselHatasi("Dosya bozuk ya da geçerli bir görsel değil.")

    # Uzantı .jpg ama içi PNG değil mi? Uzantıya değil İÇERİĞE güveniyoruz.
    # (Ör. "fis.jpg" adını verilmiş bir .exe dosyası burada reddedilir.)
    if gorsel.format != UZANTI_BICIM.get(uzanti):
        raise GorselHatasi(
            f"Dosya uzantısı (.{uzanti}) ile içeriği ({gorsel.format}) uyuşmuyor."
        )

    # Telefon fotoğrafları yan çekilince bilgisi EXIF'te tutulur.
    # exif_transpose -> görseli gerçekten çevirir (aksi halde yazılar yan durur)
    gorsel = ImageOps.exif_transpose(gorsel)

    if min(gorsel.size) < EN_KUCUK_KENAR:
        raise GorselHatasi(
            f"Çözünürlük çok düşük ({gorsel.width}x{gorsel.height} piksel). "
            f"Kısa kenar en az {EN_KUCUK_KENAR} piksel olmalı; daha yakından çekin."
        )
    return gorsel


# ---------------------------------------------------------------- 2) KALİTE ÖLÇ
def kalite_olc(gorsel):
    """
    Görselin kalitesini ölçer.

    Döndürür: (puan, uyarilar, olcumler)
        puan     -> 0-100 arası tamsayı (100 = sorunsuz)
        uyarilar -> kullanıcıya gösterilecek uyarı metinleri listesi
        olcumler -> ham ölçüm değerleri (rapor/test için)
    """
    # Ölçümü sabit boyutta yapıyoruz ki büyük ve küçük fotoğraflar karşılaştırılabilsin
    gri = ImageOps.grayscale(gorsel)
    gri.thumbnail((1000, 1000))

    # Fiş çoğunlukla BEYAZ kâğıttır, yazı az yer kaplar. Bu yüzden "ortalama"
    # yerine tonların DAĞILIMINA (histogram) bakıyoruz.
    # histogram() -> 256 elemanlı liste: her tondan (0-255) kaç piksel var
    hist = gri.histogram()
    toplam = sum(hist)
    parlaklik = ImageStat.Stat(gri).mean[0]           # ortalama parlaklık (0 siyah, 255 beyaz)
    koyu = _yuzdelik(hist, toplam, 0.002)              # en koyu binde 2'lik ton (yazının rengi)
    acik = _yuzdelik(hist, toplam, 0.99)               # en açık %1'lik ton (kâğıdın rengi)
    kontrast = acik - koyu                             # yazı ile kâğıt arasındaki fark
    patlama = sum(hist[250:]) / toplam                 # tam beyaz (ışık patlaması) oranı

    # KESKİNLİK (bulanıklık ölçüsü) - Laplace filtresi:
    # Kenarları (yazı çizgileri) parlak, düz alanları koyu yapar.
    # Sonucun varyansı (dağılımı) YÜKSEKSE görselde net kenar çoktur = keskin.
    # Bulanık görselde kenarlar yumuşar, varyans düşer.
    laplace = gri.filter(
        ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)
    )
    # Pillow filtrede en dıştaki 1 piksellik çerçeveyi işlemez; ölçümü bozmasın diye kırpıyoruz
    laplace = laplace.crop((2, 2, laplace.width - 2, laplace.height - 2))
    keskinlik = ImageStat.Stat(laplace).var[0]

    puan = 100
    uyarilar = []
    if keskinlik < COK_BULANIK_ESIGI:
        puan -= 70
        uyarilar.append("Görsel çok bulanık; yazılar okunamıyor.")
    elif keskinlik < BULANIK_ESIGI:
        puan -= 35
        uyarilar.append("Görsel bulanık görünüyor; bazı yazılar yanlış okunabilir.")
    if parlaklik < KARANLIK_ESIGI:
        puan -= 30
        uyarilar.append("Görsel çok karanlık; daha aydınlık bir ortamda çekin.")
    if patlama > PATLAMA_ORANI:
        puan -= 30
        uyarilar.append("Görselde ışık patlaması var; flaşı kapatıp yeniden çekin.")
    if kontrast < KONTRAST_ESIGI:
        puan -= 20
        uyarilar.append("Kontrast düşük (soluk görsel); otomatik olarak artırıldı.")

    olcumler = {
        "keskinlik": round(keskinlik, 1),
        "parlaklik": round(parlaklik, 1),
        "kontrast": kontrast,
        "patlama_orani": round(patlama, 3),
    }
    return max(puan, 0), uyarilar, olcumler


def _yuzdelik(hist, toplam, oran):
    """Histogramda piksellerin "oran" kadarının altında kaldığı tonu bulur (ör. %1)."""
    sinir = toplam * oran
    birikim = 0
    for ton, adet in enumerate(hist):
        birikim += adet
        if birikim >= sinir:
            return ton
    return 255


# ---------------------------------------------------------------- 3) ÖN İŞLE
def on_isle(gorsel):
    """
    Görseli OCR için hazırlar. Orijinal değiştirilmez, YENİ görsel döndürülür.

    Adımlar (her biri OCR doğruluğunu artırır):
        1) Gri tonlama   -> renk bilgisi metin okumaya katkı vermez, işi 3 kat azaltır
        2) Küçültme      -> uzun kenar en fazla 2000 piksel (yeterli ve hızlı)
        3) Otomatik kontrast -> en koyu tonu siyaha, en açığı beyaza çeker
                             (gölgeli/soluk fişlerde yazı belirginleşir)
        4) Keskinleştirme -> harf kenarlarını netleştirir
    """
    islenmis = ImageOps.grayscale(gorsel)

    # thumbnail -> en-boy oranını koruyarak küçültür; zaten küçükse dokunmaz
    # LANCZOS -> küçültmede en kaliteli yeniden örnekleme yöntemi
    islenmis.thumbnail((EN_BUYUK_KENAR, EN_BUYUK_KENAR), Image.Resampling.LANCZOS)

    # cutoff=1 -> en uçtaki %1'lik tonları yok say (tek bir parlak leke ayarı bozmasın)
    islenmis = ImageOps.autocontrast(islenmis, cutoff=1)

    # UnsharpMask: radius=yarıçap, percent=güç, threshold=küçük farkları (gürültüyü) atla
    islenmis = islenmis.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))
    return islenmis


# ---------------------------------------------------------------- 4) ÖNİZLEME
def kucuk_resim(gorsel, boyut=320):
    """Listede gösterilecek küçük önizleme (renkli, en fazla 320 piksel)."""
    kucuk = gorsel.convert("RGB")  # PNG'deki saydamlık JPEG'e yazılamaz
    kucuk.thumbnail((boyut, boyut))
    return kucuk


def bayta_cevir(gorsel, bicim):
    """Pillow görselini diske yazılacak baytlara çevirir. bicim: "PNG" veya "JPEG"."""
    tampon = io.BytesIO()
    gorsel.save(tampon, format=bicim, **({"quality": 85} if bicim == "JPEG" else {}))
    return tampon.getvalue()


# ---------------------------------------------------------------- HEPSİ BİR ARADA
def isle(veri, uzanti):
    """
    Bir görsel dosyası için tüm akışı çalıştırır.

    Döndürür (sözlük):
        islenmis_png -> OCR'a gidecek ön işlenmiş görsel (PNG baytları)
        kucuk_jpg    -> önizleme (JPEG baytları)
        genislik, yukseklik, kalite_puani, uyarilar, olcumler
    Hata:
        GorselHatasi -> görsel kaydedilmeye uygun değil
    """
    gorsel = gorsel_ac(veri, uzanti)
    puan, uyarilar, olcumler = kalite_olc(gorsel)

    if puan < EN_DUSUK_PUAN:
        raise GorselHatasi(
            "Görsel okunamayacak kadar düşük kaliteli: " + " ".join(uyarilar)
            + " Lütfen fotoğrafı yeniden çekin."
        )

    return {
        "islenmis_png": bayta_cevir(on_isle(gorsel), "PNG"),
        "kucuk_jpg": bayta_cevir(kucuk_resim(gorsel), "JPEG"),
        "genislik": gorsel.width,
        "yukseklik": gorsel.height,
        "kalite_puani": puan,
        "uyarilar": uyarilar,
        "olcumler": olcumler,
    }
