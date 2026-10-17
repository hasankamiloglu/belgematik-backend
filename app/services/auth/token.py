"""
token.py - JWT (JSON Web Token) üretme ve çözme.

OTURUM (session) ile TOKEN farkı:
    Oturum -> Bilgi SUNUCUDA tutulur, tarayıcıya sadece bir "oturum numarası"
              (çerez/cookie) verilir. Sunucu her istekte bu numarayı kendi
              hafızasında arar.
    Token  -> Bilgi TOKENIN İÇİNDE taşınır ve sunucunun gizli anahtarıyla
              İMZALANIR. Sunucu hafızasında bir şey aramaz, sadece imzayı
              kontrol eder. Frontend ve backend ayrı olduğu için (React + API)
              token yöntemini seçtik.

JWT'nin 3 parçası (nokta ile ayrılır):  BAŞLIK.İÇERİK.İMZA
    İçerik (payload) şifreli DEĞİLDİR, herkes okuyabilir -> içine parola vb. KONMAZ.
    İmza sayesinde içerik DEĞİŞTİRİLEMEZ: biri "yetki": "yonetici" yazarsa
    imza tutmaz ve token reddedilir.

Kütüphane: PyJWT  (pip install PyJWT  ->  import jwt)
"""

from datetime import datetime, timedelta, timezone

import jwt

ALGORITMA = "HS256"  # HMAC + SHA-256: aynı gizli anahtarla imzala ve doğrula


def token_olustur(kullanici, gizli_anahtar, sure_dakika=60):
    """
    Giriş başarılı olunca kullanıcıya verilecek token'ı üretir.

    Parametreler:
        kullanici     -> veritabanından gelen kullanıcı satırı (dict)
        gizli_anahtar -> .env içindeki SECRET_KEY (imza için)
        sure_dakika   -> token kaç dakika geçerli (oturum süresi)
    Döndürür:
        "eyJhbGciOi..." biçiminde token metni
    """
    simdi = datetime.now(timezone.utc)
    icerik = {
        "sub": str(kullanici["id"]),         # subject: token kime ait (kullanıcı id)
        "yetki": kullanici["yetki"],          # kullanici / yonetici
        "sv": kullanici["token_surumu"],      # token sürümü (çıkışta artar)
        "iat": simdi,                         # issued at: üretilme zamanı
        "exp": simdi + timedelta(minutes=sure_dakika),  # expires: son geçerlilik
    }
    return jwt.encode(icerik, gizli_anahtar, algorithm=ALGORITMA)


def token_coz(token, gizli_anahtar):
    """
    Token'ın imzasını ve süresini kontrol eder, içeriğini döndürür.

    Hata durumları (jwt kütüphanesi fırlatır):
        jwt.ExpiredSignatureError -> süresi dolmuş
        jwt.InvalidTokenError     -> imza yanlış / token bozuk / değiştirilmiş
    algorithms=[ALGORITMA] -> sadece bizim algoritmamızı kabul et
    ("alg: none" gibi imzasız token hilelerini engeller).
    """
    return jwt.decode(token, gizli_anahtar, algorithms=[ALGORITMA])
