"""
belge_servisi.py - Belge yükleme, listeleme, görüntüleme ve silme (İŞ katmanı, Hafta 6).

    API (app/api/belgeler.py)  ->  belge_servisi  ->  preprocessing/goruntu.py (görsel işleme)
                                                  ->  belge_repo / kullanici_repo (veritabanı)
                                                  ->  disk (uploads/ klasörü)

İŞ KURALLARI (hepsi bu dosyada, SUNUCUDA uygulanır):
    1) Sadece png / jpg / jpeg / pdf kabul edilir; uzantı İÇERİKLE uyuşmalı.
    2) En fazla 10 MB (Flask ayrıca 413 ile durdurur).
    3) Görsel kalitesi ölçülür: çok kötü ise reddedilir, orta ise uyarıyla kaydedilir.
    4) Aynı kullanıcı aynı dosyayı iki kez yükleyemez (SHA-256 parmak izi).
    5) Her yükleme 1 kredi harcar; kredisi biten yükleyemez.
       Kayıt + kredi düşme TEK TRANSACTION'dadır (biri olmazsa ikisi de olmaz).
    6) Her kullanıcı sadece KENDİ belgelerini görebilir/silebilir (sahiplik).
"""

import hashlib
import json
import logging
import os
import uuid

from psycopg import errors as db_hatalari

from app.data.db import baglanti
from app.data.models import DOSYA_TURLERI
from app.data.repositories import belge_repo, kullanici_repo
from app.services.preprocessing import goruntu

EN_BUYUK_BOYUT = 10 * 1024 * 1024  # 10 MB (config.py MAX_CONTENT_LENGTH ile aynı)
GORSEL_TURLERI = ("png", "jpg", "jpeg")


class BelgeHatasi(Exception):
    """Belge işlemlerindeki beklenen hatalar. durum_kodu -> HTTP kodu (400, 402, 404, 409)."""

    def __init__(self, mesaj, durum_kodu=400):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.durum_kodu = durum_kodu


# ------------------------------------------------------------------ yardımcılar
def _uzanti(dosya_adi):
    """'Fis.JPG' -> 'jpg'. Uzantı yoksa boş metin."""
    return dosya_adi.rsplit(".", 1)[-1].lower() if "." in dosya_adi else ""


def _guvenli_ad(dosya_adi):
    """
    Kullanıcının verdiği dosya adını SADECE GÖSTERMEK için temizler.
    Diske bu adla YAZMIYORUZ (bkz. yukle: rastgele uuid ad verilir). Böylece
    "../../config.py" gibi bir adla sunucudaki başka dosyaların üzerine yazılamaz.
    """
    ad = os.path.basename((dosya_adi or "").replace("\\", "/")).strip()
    return ad[:200] or "adsiz"


def disari(belge):
    """Veritabanı satırını API cevabına çevirir (tarih -> ISO metin, uyarılar -> liste)."""
    sonuc = {k: belge[k] for k in (
        "id", "dosya_adi", "dosya_turu", "boyut_kb", "durum", "genislik",
        "yukseklik", "kalite_puani", "on_islenmis",
    )}
    tarih = belge["yuklenme_tarihi"]
    sonuc["yuklenme_tarihi"] = tarih.isoformat() if hasattr(tarih, "isoformat") else tarih
    uyarilar = belge["kalite_uyarilari"]
    sonuc["kalite_uyarilari"] = json.loads(uyarilar) if isinstance(uyarilar, str) else (uyarilar or [])
    return sonuc


# ===================================================================== YÜKLE
def yukle(kullanici_id, dosya_adi, veri, yukleme_klasoru):
    """
    Bir dosyayı doğrular, ön işler, diske yazar ve veritabanına kaydeder.

    Parametreler:
        kullanici_id    -> giriş yapan kullanıcı (token'dan)
        dosya_adi       -> tarayıcının gönderdiği orijinal dosya adı
        veri            -> dosyanın baytları
        yukleme_klasoru -> config.py'deki UPLOAD_FOLDER
    Döndürür: {"belge": {...}, "kalan_kredi": 19}
    """
    # ---- 1) Temel doğrulama (ucuz kontroller önce)
    dosya_adi = _guvenli_ad(dosya_adi)
    uzanti = _uzanti(dosya_adi)
    if uzanti not in DOSYA_TURLERI:
        raise BelgeHatasi("Sadece PNG, JPG/JPEG veya PDF dosyası yükleyebilirsiniz.")
    if not veri:
        raise BelgeHatasi("Dosya boş.")
    if len(veri) > EN_BUYUK_BOYUT:
        raise BelgeHatasi("Dosya 10 MB'tan büyük olamaz.", 413)

    # SHA-256 -> dosyanın parmak izi. Tek bayt değişse bile tamamen farklı olur.
    dosya_hash = hashlib.sha256(veri).hexdigest()

    # ---- 2) Veritabanı kuralları: aynı dosya mı? kredi var mı?
    with baglanti() as conn:
        onceki = belge_repo.hash_ile_bul(conn, kullanici_id, dosya_hash)
        if onceki:
            raise BelgeHatasi(
                f"Bu dosyayı zaten yüklediniz (\"{onceki['dosya_adi']}\", belge #{onceki['id']}).", 409
            )
        if kullanici_repo.kalan_kredi(conn, kullanici_id) <= 0:
            raise BelgeHatasi("Bu ayki krediniz bitti. Pro pakete geçebilirsiniz.", 402)

    # ---- 3) Ön işleme (görsel) veya içerik kontrolü (PDF)
    if uzanti in GORSEL_TURLERI:
        try:
            sonuc = goruntu.isle(veri, uzanti)
        except goruntu.GorselHatasi as h:
            raise BelgeHatasi(h.mesaj, 400)
    else:
        # PDF dosyaları "%PDF-" ile başlar. Değilse uzantı sahtedir.
        if not veri.startswith(b"%PDF-"):
            raise BelgeHatasi("Dosya uzantısı .pdf ama içeriği PDF değil.")
        sonuc = None  # PDF'ten görsel üretme OCR haftasında eklenecek

    # ---- 4) Diske yaz. Ad RASTGELE (uuid): tahmin edilemez, çakışmaz, kullanıcı adı kullanılmaz.
    #         Her kullanıcının ayrı klasörü var: uploads/<kullanici_id>/
    ad = uuid.uuid4().hex
    goreli = lambda ek: f"{kullanici_id}/{ad}{ek}"  # noqa: E731  (veritabanına yazılan yol)
    yazilacaklar = {goreli(f".{uzanti}"): veri}
    if sonuc:
        yazilacaklar[goreli("_islenmis.png")] = sonuc["islenmis_png"]
        yazilacaklar[goreli("_kucuk.jpg")] = sonuc["kucuk_jpg"]

    os.makedirs(os.path.join(yukleme_klasoru, str(kullanici_id)), exist_ok=True)
    for yol, bayt in yazilacaklar.items():
        with open(os.path.join(yukleme_klasoru, yol), "wb") as f:  # "wb" -> bayt olarak yaz
            f.write(bayt)

    bilgi = {
        "dosya_adi": dosya_adi,
        "dosya_yolu": goreli(f".{uzanti}"),
        "dosya_turu": uzanti,
        "boyut_kb": max(1, round(len(veri) / 1024)),
        "durum": "on_islendi" if sonuc else "yuklendi",
        "dosya_hash": dosya_hash,
        "islenmis_yol": goreli("_islenmis.png") if sonuc else None,
        "kucuk_yol": goreli("_kucuk.jpg") if sonuc else None,
        "genislik": sonuc["genislik"] if sonuc else None,
        "yukseklik": sonuc["yukseklik"] if sonuc else None,
        "kalite_puani": sonuc["kalite_puani"] if sonuc else None,
        "kalite_uyarilari": sonuc["uyarilar"] if sonuc else [],
    }

    # ---- 5) Kayıt + kredi düşme: TEK TRANSACTION (ya ikisi ya hiçbiri)
    try:
        with baglanti() as conn:
            with conn.transaction():
                belge = belge_repo.yukleme_kaydet(conn, kullanici_id, bilgi)
                kredi = kullanici_repo.kredi_dus(conn, kullanici_id, 1)
                if kredi is None:  # aboneliği yok
                    raise db_hatalari.CheckViolation("abonelik yok")
    except (db_hatalari.CheckViolation, db_hatalari.UniqueViolation) as h:
        # Veritabanı reddetti -> diske yazılan dosyaları da geri al (yarım iş kalmasın)
        for yol in yazilacaklar:
            _dosya_sil(yukleme_klasoru, yol)
        if isinstance(h, db_hatalari.UniqueViolation):
            raise BelgeHatasi("Bu dosyayı zaten yüklediniz.", 409)
        raise BelgeHatasi("Bu ayki krediniz bitti. Pro pakete geçebilirsiniz.", 402)

    return {"belge": disari(belge), "kalan_kredi": kredi["kalan_kredi"]}


# ================================================================== LİSTELE
def listele(kullanici_id):
    """Kullanıcının KENDİ belgeleri (en yeni en üstte) ve kalan kredisi."""
    with baglanti() as conn:
        belgeler = belge_repo.kullaniciya_gore_listele(conn, kullanici_id, limit=100)
        kredi = kullanici_repo.kalan_kredi(conn, kullanici_id)
    return {"belgeler": [disari(b) for b in belgeler], "kalan_kredi": kredi}


def getir(kullanici_id, belge_id):
    """Tek belge. Başkasına aitse veya yoksa 404 (varlığı bile söylenmez)."""
    with baglanti() as conn:
        belge = belge_repo.sahibine_ait_getir(conn, belge_id, kullanici_id)
    if belge is None:
        raise BelgeHatasi("Belge bulunamadı.", 404)
    return belge


# ================================================================== GÖRSEL
def gorsel_yolu(kullanici_id, belge_id, tur, yukleme_klasoru):
    """
    Belgenin diskteki dosya yolunu döndürür (sahiplik kontrolüyle).
        tur -> "orijinal", "islenmis" veya "kucuk"
    """
    kolon = {"orijinal": "dosya_yolu", "islenmis": "islenmis_yol", "kucuk": "kucuk_yol"}.get(tur)
    if kolon is None:
        raise BelgeHatasi("tur 'orijinal', 'islenmis' veya 'kucuk' olmalı.")
    belge = getir(kullanici_id, belge_id)

    goreli = belge[kolon]
    if not goreli:
        raise BelgeHatasi("Bu belge için istenen görsel yok.", 404)
    tam_yol = os.path.abspath(os.path.join(yukleme_klasoru, goreli))
    # Güvenlik: yol uploads klasörünün DIŞINA çıkmamalı
    if os.path.commonpath([tam_yol, os.path.abspath(yukleme_klasoru)]) != os.path.abspath(yukleme_klasoru):
        raise BelgeHatasi("Geçersiz dosya yolu.", 404)
    if not os.path.exists(tam_yol):
        raise BelgeHatasi("Dosya sunucuda bulunamadı (örnek veriler için normaldir).", 404)
    return tam_yol


# ===================================================================== SİL
def sil(kullanici_id, belge_id, yukleme_klasoru):
    """
    Belgeyi siler: önce sahiplik kontrolü, sonra veritabanı, sonra diskteki dosyalar.
    Not (iş kuralı): Harcanan kredi iade edilmez; işlem zaten yapılmıştır.
    """
    belge = getir(kullanici_id, belge_id)
    with baglanti() as conn:
        belge_repo.sil(conn, belge_id)
    for kolon in ("dosya_yolu", "islenmis_yol", "kucuk_yol"):
        if belge[kolon]:
            _dosya_sil(yukleme_klasoru, belge[kolon])


def _dosya_sil(klasor, goreli):
    """
    Dosya varsa siler; yoksa sessizce geçer.
    Silinemezse (ör. Windows'ta başka bir program dosyayı açık tutuyorsa) işlemi
    çökertmez, sadece uyarı günlüğe yazılır. Veritabanı kaydı zaten silinmiştir.
    """
    try:
        os.remove(os.path.join(klasor, goreli))
    except FileNotFoundError:
        pass
    except OSError as h:
        logging.getLogger(__name__).warning("Dosya silinemedi: %s (%s)", goreli, h)
