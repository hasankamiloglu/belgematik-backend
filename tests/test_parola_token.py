"""
test_parola_token.py - Parola hash'leme ve JWT token testleri.
Veritabanı GEREKMEZ.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.services.auth import parola, token

GIZLI = "test-gizli-anahtar-en-az-32-karakter-uzunlukta"


# ------------------------------------------------------------------ parola
def test_parola_duz_metin_saklanmiyor():
    """Hash'in içinde parolanın kendisi geçmemeli."""
    h = parola.hash_olustur("Deneme123")
    assert "Deneme123" not in h
    assert h.startswith("pbkdf2_sha256$")


def test_ayni_parola_farkli_tuz_farkli_hash():
    """Tuz sayesinde aynı parolanın iki hash'i FARKLI olmalı."""
    h1 = parola.hash_olustur("Deneme123")
    h2 = parola.hash_olustur("Deneme123")
    assert h1 != h2
    # tuz kısmı (3. parça) da farklı olmalı
    assert h1.split("$")[2] != h2.split("$")[2]


def test_dogru_ve_yanlis_parola():
    h = parola.hash_olustur("Deneme123")
    assert parola.dogrula("Deneme123", h) is True
    assert parola.dogrula("deneme123", h) is False  # büyük/küçük harf önemli
    assert parola.dogrula("", h) is False


def test_bozuk_hash_giris_vermez():
    """Biçimi bozuk kayıt (ör. eski 'sahte-hash') ile asla giriş yapılamamalı."""
    assert parola.dogrula("herhangi", "sahte-hash-1") is False
    assert parola.dogrula("herhangi", None) is False


@pytest.mark.parametrize(
    "deneme, hata_var",
    [("kisa1", True), ("sadeceharf", True), ("12345678", True), ("Deneme123", False)],
)
def test_parola_kurallari(deneme, hata_var):
    """En az 8 karakter, en az bir harf ve bir rakam."""
    assert bool(parola.parola_kurallari(deneme)) is hata_var


# ------------------------------------------------------------------- token
KULLANICI = {"id": 7, "yetki": "kullanici", "token_surumu": 0}


def test_token_uret_ve_coz():
    t = token.token_olustur(KULLANICI, GIZLI, 60)
    icerik = token.token_coz(t, GIZLI)
    assert icerik["sub"] == "7"
    assert icerik["yetki"] == "kullanici"


def test_suresi_dolmus_token_reddedilir():
    t = token.token_olustur(KULLANICI, GIZLI, sure_dakika=-1)  # 1 dk önce dolmuş
    with pytest.raises(jwt.ExpiredSignatureError):
        token.token_coz(t, GIZLI)


def test_baska_anahtarla_imzalanan_token_reddedilir():
    t = token.token_olustur(KULLANICI, "baska-bir-anahtar-en-az-32-karakter-uzun", 60)
    with pytest.raises(jwt.InvalidTokenError):
        token.token_coz(t, GIZLI)


def test_icerigi_degistirilen_token_reddedilir():
    """Saldırgan token içinde yetkiyi 'yonetici' yapıp kendi imzalarsa reddedilmeli."""
    sahte = jwt.encode(
        {"sub": "7", "yetki": "yonetici", "sv": 0,
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "saldirganin-anahtari-en-az-32-karakter-uzun", algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        token.token_coz(sahte, GIZLI)
