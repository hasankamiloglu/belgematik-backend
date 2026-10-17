"""
kimlik_servisi.py - Kayıt, giriş, oturum ve çıkış akışı (İŞ katmanı).

API katmanı (app/api/kimlik.py) SADECE bu dosyadaki fonksiyonları çağırır;
SQL bilmez. Bu dosya da SQL yazmaz; veri katmanındaki repository'leri kullanır.

    API  ->  kimlik_servisi  ->  kullanici_repo / kimlik_repo  ->  PostgreSQL

Hatalar KimlikHatasi ile bildirilir; API katmanı bunu JSON hata cevabına çevirir.
"""

import re

import jwt
from psycopg import errors as db_hatalari

from app.data.db import baglanti
from app.data.models import ROLLER
from app.data.repositories import kimlik_repo, kullanici_repo
from app.services.auth import parola as parola_araci
from app.services.auth import token as token_araci

# Başarısız girişte HER DURUMDA aynı mesaj verilir. "Böyle bir e-posta yok" ile
# "parola yanlış" ayrı söylenirse saldırgan hangi e-postaların kayıtlı olduğunu öğrenir.
GENEL_GIRIS_HATASI = "E-posta veya parola hatalı."

# Olmayan e-postayla giriş denendiğinde de bir hash hesaplanır; böylece cevap süresi
# "e-posta var" durumuyla aynı olur ve süreden ipucu çıkmaz.
_SAHTE_HASH = parola_araci.hash_olustur("zamanlama-esitleme-icin")

# Basit e-posta kalıbı:  bir_sey @ bir_sey . bir_sey  (boşluk yok)
EMAIL_KALIBI = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class KimlikHatasi(Exception):
    """
    Kimlik işlemlerindeki beklenen hatalar.
        mesaj      -> kullanıcıya gösterilecek açıklama
        durum_kodu -> HTTP durum kodu (400, 401, 403, 409, 429)
        ayrintilar -> (isteğe bağlı) hata listesi, ör. parola kuralları
    """

    def __init__(self, mesaj, durum_kodu=400, ayrintilar=None):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.durum_kodu = durum_kodu
        self.ayrintilar = ayrintilar or []


# ------------------------------------------------------------------ yardımcılar
def _email_duzenle(email):
    """E-postayı karşılaştırılabilir hale getirir: boşlukları sil, küçük harfe çevir."""
    return (email or "").strip().lower()


def guvenli_bilgi(satir):
    """
    Veritabanı satırından frontend'e gönderilebilecek alanları seçer.
    sifre_hash, token_surumu, basarisiz_giris gibi alanlar ASLA dışarı çıkmaz.
    Tarihler ISO biçimine çevrilir: 2026-10-17T21:30:00+00:00
    """
    izinli = ("id", "ad_soyad", "email", "rol", "yetki", "paket", "kalan_kredi",
              "son_giris", "olusturma_tarihi")
    sonuc = {}
    for alan in izinli:
        if alan in satir:
            deger = satir[alan]
            sonuc[alan] = deger.isoformat() if hasattr(deger, "isoformat") else deger
    return sonuc


# ------------------------------------------------------------------- KAYIT
def kayit_ol(ad_soyad, email, parola, rol="bireysel"):
    """
    Yeni kullanıcı kaydı.

    Adımlar:
        1) Girdileri kontrol et (boş mu, e-posta biçimi, rol, parola kuralları)
        2) Parolayı hash'le (düz parola hiçbir yere yazılmaz)
        3) Kullanıcı + ücretsiz aboneliği tek transaction ile kaydet
    Yetki her zaman 'kullanici' başlar; istekte "yetki" gönderilse bile dikkate ALINMAZ.
    Döndürür: güvenli kullanıcı bilgisi (dict)
    """
    ad_soyad = (ad_soyad or "").strip()
    email = _email_duzenle(email)
    parola = parola or ""

    hatalar = []
    if not (2 <= len(ad_soyad) <= 100):
        hatalar.append("Ad soyad 2-100 karakter olmalı.")
    if not EMAIL_KALIBI.match(email) or len(email) > 255:
        hatalar.append("Geçerli bir e-posta adresi girin.")
    if rol not in ROLLER:
        hatalar.append(f"Hesap türü şunlardan biri olmalı: {', '.join(ROLLER)}.")
    hatalar += parola_araci.parola_kurallari(parola)
    if hatalar:
        raise KimlikHatasi("Kayıt bilgileri geçersiz.", 400, hatalar)

    sifre_hash = parola_araci.hash_olustur(parola)

    with baglanti() as conn:
        if kimlik_repo.giris_icin_getir(conn, email):
            raise KimlikHatasi("Bu e-posta ile zaten bir hesap var.", 409)
        try:
            kullanici = kullanici_repo.abonelikli_ekle(conn, ad_soyad, email, sifre_hash, rol)
        except db_hatalari.UniqueViolation:
            # Aynı anda iki kayıt isteği gelirse UNIQUE kısıtı ikincisini durdurur
            raise KimlikHatasi("Bu e-posta ile zaten bir hesap var.", 409)
    return guvenli_bilgi(kullanici)


# ------------------------------------------------------------------- GİRİŞ
def giris_yap(email, parola, ip_adresi, gizli_anahtar,
              sure_dakika=60, deneme_siniri=5, kilit_dakika=15):
    """
    E-posta + parola ile giriş. Başarılıysa token üretir.

    Parametreler:
        ip_adresi     -> isteğin geldiği adres (günlüğe yazılır)
        gizli_anahtar -> token imzası için SECRET_KEY
        sure_dakika   -> token (oturum) süresi
        deneme_siniri -> kaç hatalı denemede hesap kilitlensin
        kilit_dakika  -> kilit kaç dakika sürsün

    BAŞARISIZ GİRİŞTE NE OLUR?
        - Her durumda aynı genel mesaj döner (401)
        - Deneme giris_denemeleri tablosuna yazılır
        - Hatalı parola sayacı artar; sınıra ulaşınca hesap kilitlenir (429)
    """
    email = _email_duzenle(email)
    parola = parola or ""

    with baglanti() as conn:
        kullanici = kimlik_repo.giris_icin_getir(conn, email)

        # 1) Böyle bir kullanıcı yok -> yine de hash hesapla (süre eşit olsun), genel mesaj ver
        if kullanici is None:
            parola_araci.dogrula(parola, _SAHTE_HASH)
            kimlik_repo.giris_denemesi_kaydet(conn, email, False, ip_adresi)
            raise KimlikHatasi(GENEL_GIRIS_HATASI, 401)

        # 2) Hesap kilitli -> parola doğru olsa bile içeri alma
        if kullanici["kilitli_mi"]:
            kimlik_repo.giris_denemesi_kaydet(conn, email, False, ip_adresi)
            raise KimlikHatasi(_kilit_mesaji(kilit_dakika), 429)

        # 3) Parola yanlış -> sayacı artır, gerekirse kilitle
        if not parola_araci.dogrula(parola, kullanici["sifre_hash"]):
            durum = kimlik_repo.basarisiz_giris_kaydet(
                conn, kullanici["id"], deneme_siniri, kilit_dakika
            )
            kimlik_repo.giris_denemesi_kaydet(conn, email, False, ip_adresi)
            if durum["kilitli_mi"]:
                raise KimlikHatasi(_kilit_mesaji(kilit_dakika), 429)
            raise KimlikHatasi(GENEL_GIRIS_HATASI, 401)

        # 4) Başarılı -> sayacı sıfırla, günlüğe yaz, token üret
        kimlik_repo.basarili_giris_kaydet(conn, kullanici["id"])
        kimlik_repo.giris_denemesi_kaydet(conn, email, True, ip_adresi)
        bilgi = kimlik_repo.oturum_icin_getir(conn, kullanici["id"])

    token = token_araci.token_olustur(bilgi, gizli_anahtar, sure_dakika)
    return {"token": token, "sure_dakika": sure_dakika, "kullanici": guvenli_bilgi(bilgi)}


def _kilit_mesaji(kilit_dakika):
    return f"Çok fazla hatalı deneme. Hesap güvenlik için {kilit_dakika} dakika kilitlendi."


# ------------------------------------------------------------------ OTURUM
def token_ile_kullanici(token, gizli_anahtar):
    """
    Her korumalı istekte çağrılır: token geçerli mi, kime ait?

    Kontroller:
        1) İmza doğru mu? (değiştirilmiş token reddedilir)
        2) Süresi dolmuş mu? (exp)
        3) Kullanıcı hâlâ var mı?
        4) Token sürümü güncel mi? (çıkış yapıldıysa eski token geçersiz)
    Döndürür: güvenli kullanıcı bilgisi (yetki dahil)
    """
    try:
        icerik = token_araci.token_coz(token, gizli_anahtar)
    except jwt.ExpiredSignatureError:
        raise KimlikHatasi("Oturum süresi doldu. Lütfen tekrar giriş yapın.", 401)
    except jwt.InvalidTokenError:
        raise KimlikHatasi("Geçersiz oturum bilgisi. Lütfen tekrar giriş yapın.", 401)

    with baglanti() as conn:
        kullanici = kimlik_repo.oturum_icin_getir(conn, int(icerik["sub"]))

    if kullanici is None or kullanici["token_surumu"] != icerik.get("sv"):
        raise KimlikHatasi("Oturum sonlandırılmış. Lütfen tekrar giriş yapın.", 401)
    return guvenli_bilgi(kullanici)


def cikis_yap(kullanici_id):
    """Çıkış: token sürümünü artırır, kullanıcının elindeki tüm token'lar geçersiz olur."""
    with baglanti() as conn:
        kimlik_repo.token_surumunu_artir(conn, kullanici_id)


# ---------------------------------------------------------------- YÖNETİCİ
def yonetici_ozeti():
    """Yönetici paneli: tüm kullanıcılar + son giriş denemeleri."""
    with baglanti() as conn:
        kullanicilar = kullanici_repo.listele(conn)
        denemeler = kimlik_repo.son_denemeler(conn)
    return {
        "kullanicilar": [guvenli_bilgi(k) for k in kullanicilar],
        "son_giris_denemeleri": [
            # tarih -> ISO metne çevrilir (JSON'da tarih tipi yoktur)
            {**d, "tarih": d["tarih"].isoformat() if hasattr(d["tarih"], "isoformat") else d["tarih"]}
            for d in denemeler
        ],
    }


def yetki_ver(email, yetki="yonetici"):
    """manage.py tarafından kullanılır: bir hesabı yönetici yapar (veya geri alır)."""
    if yetki not in ("kullanici", "yonetici"):
        raise KimlikHatasi("Yetki 'kullanici' veya 'yonetici' olmalı.")
    with baglanti() as conn:
        return kimlik_repo.yetki_ver(conn, _email_duzenle(email), yetki)
