"""
parola.py - Parola hash'leme ve doğrulama (kendi yazdığımız akış).

NEDEN HASH?
    Veritabanı çalınırsa parolalar okunamasın diye parolanın KENDİSİ değil,
    geri döndürülemeyen "parmak izi" (hash) saklanır.
    Giriş yaparken: girilen parola aynı yöntemle tekrar hash'lenir ve
    kayıtlı hash ile karşılaştırılır. Parolanın aslı hiçbir yerde tutulmaz.

TUZ (SALT) NEDİR?
    Her kullanıcı için üretilen RASTGELE bir değerdir; parolaya eklenip öyle hash'lenir.
    - Aynı parolayı kullanan iki kişinin hash'i FARKLI olur.
    - Saldırgan hazır "parola -> hash" tablolarını (rainbow table) kullanamaz.
    Tuz gizli değildir; hash ile birlikte veritabanında saklanır.

YÖNTEM: PBKDF2-HMAC-SHA256, 600.000 tekrar (OWASP 2023 önerisi)
    Hash işlemi bilerek YAVAŞ yapılır (600 bin kez tekrarlanır).
    Kullanıcı için 0,3 saniye fark etmez; ama milyonlarca parola deneyen
    saldırganı çok yavaşlatır.
    Python'un kendi "hashlib" modülü kullanıldığı için ek kurulum gerekmez.
    (bcrypt da aynı mantıkla çalışan, yaygın bir alternatiftir.)

SAKLANAN BİÇİM (tek metin, "$" ile ayrılmış 4 parça):
    pbkdf2_sha256$600000$<tuz>$<hash>
    yöntem       tekrar   tuz   sonuç
"""

import hashlib
import hmac
import os
import re
import secrets

YONTEM = "pbkdf2_sha256"

# Tekrar sayısı. Testleri hızlandırmak için tests/conftest.py bunu küçültür.
# Kayıtlı hash'in içinde kendi tekrar sayısı yazdığı için değer sonradan
# artırılsa bile eski parolalar doğrulanmaya devam eder.
ITERASYON = int(os.getenv("PAROLA_ITERASYON", "600000"))

EN_AZ_UZUNLUK = 8


def hash_olustur(parola):
    """
    Parolayı tuzlayıp hash'ler ve veritabanına yazılacak metni döndürür.

    Parametre:
        parola -> kullanıcının yazdığı düz parola (str)
    Döndürür:
        "pbkdf2_sha256$600000$<tuz>$<hash>" biçiminde metin
    """
    # secrets.token_hex(16) -> kriptografik olarak güvenli 16 baytlık rastgele tuz
    tuz = secrets.token_hex(16)
    sonuc = _hesapla(parola, tuz, ITERASYON)
    return f"{YONTEM}${ITERASYON}${tuz}${sonuc}"


def dogrula(parola, kayitli_hash):
    """
    Girilen parola, kayıtlı hash ile eşleşiyor mu?

    Parametreler:
        parola       -> giriş ekranında yazılan parola
        kayitli_hash -> veritabanındaki sifre_hash değeri
    Döndürür:
        True (doğru parola) / False (yanlış parola veya bozuk kayıt)
    """
    try:
        yontem, tekrar, tuz, beklenen = kayitli_hash.split("$")
    except (AttributeError, ValueError):
        return False  # biçim bozuk (ör. örnek verideki "sahte-hash") -> giriş yok
    if yontem != YONTEM:
        return False

    # Kayıttaki TUZ ve TEKRAR sayısıyla aynı hesabı yap
    hesaplanan = _hesapla(parola, tuz, int(tekrar))

    # hmac.compare_digest -> iki metni SABİT sürede karşılaştırır.
    # Normal "==" ilk farklı karakterde durur; süre farkından ipucu sızabilir
    # (zamanlama saldırısı). compare_digest bunu engeller.
    return hmac.compare_digest(hesaplanan, beklenen)


def _hesapla(parola, tuz, tekrar):
    """
    PBKDF2 hesabını yapar (iç yardımcı fonksiyon).
        "sha256"        -> kullanılan hash algoritması
        parola.encode() -> metni bayta çevirir (hash fonksiyonları bayt ister)
        tekrar          -> kaç kez tekrar edileceği (yavaşlatma)
    .hex() -> sonucu okunabilir onaltılık (hex) metne çevirir.
    """
    return hashlib.pbkdf2_hmac("sha256", parola.encode("utf-8"), tuz.encode("utf-8"), tekrar).hex()


def parola_kurallari(parola):
    """
    Parolanın güçlülük kurallarını kontrol eder.
    Döndürür: hata mesajları listesi. Boş liste -> parola uygun.
    """
    hatalar = []
    if len(parola) < EN_AZ_UZUNLUK:
        hatalar.append(f"Parola en az {EN_AZ_UZUNLUK} karakter olmalı.")
    if len(parola) > 128:
        hatalar.append("Parola en fazla 128 karakter olabilir.")
    # re.search -> metinde kalıp arar. [A-Za-zÇĞİÖŞÜçğıöşü] -> herhangi bir harf
    if not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", parola):
        hatalar.append("Parola en az bir harf içermeli.")
    if not re.search(r"\d", parola):  # \d -> rakam
        hatalar.append("Parola en az bir rakam içermeli.")
    return hatalar
