"""
kullanici_repo.py - kullanicilar ve abonelikler tabloları için CRUD fonksiyonları.

ÖNEMLİ - %s yer tutucusu (parametreli sorgu):
    YANLIŞ:  conn.execute(f"SELECT * FROM kullanicilar WHERE email = '{email}'")
    DOĞRU :  conn.execute("SELECT * FROM kullanicilar WHERE email = %s", (email,))
    Yanlış yöntemde kötü niyetli biri email yerine  ' OR '1'='1  yazarsa tüm
    kullanıcıları çekebilir (SQL injection). %s ile değer, veritabanına SQL'den
    AYRI gönderilir ve asla komut olarak çalıştırılmaz.

RETURNING * -> INSERT/UPDATE/DELETE sonrası etkilenen satırı geri döndürür;
               tekrar SELECT yapmaya gerek kalmaz.
"""

# Ücretsiz pakette verilen aylık kredi (bir kredi = bir belge işleme hakkı)
UCRETSIZ_AYLIK_KREDI = 20


# ----------------------------------------------------------------- CREATE
def ekle(conn, ad_soyad, email, sifre_hash, rol="bireysel"):
    """Yeni kullanıcı ekler ve eklenen satırı (id dahil) döndürür."""
    return conn.execute(
        """
        INSERT INTO kullanicilar (ad_soyad, email, sifre_hash, rol)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (ad_soyad, email, sifre_hash, rol),
    ).fetchone()


def abonelikli_ekle(conn, ad_soyad, email, sifre_hash, rol="bireysel"):
    """
    Kullanıcıyı VE ücretsiz aboneliğini TEK TRANSACTION içinde ekler.

    Neden transaction? İki INSERT birbirine bağlı: aboneliği olmayan kullanıcı
    istemiyoruz. İkinci INSERT hata verirse birincisi de geri alınır (ROLLBACK).
    Ya ikisi birden kaydedilir ya hiçbiri -> "ya hep ya hiç" (atomiklik).
    """
    with conn.transaction():
        kullanici = ekle(conn, ad_soyad, email, sifre_hash, rol)
        conn.execute(
            """
            INSERT INTO abonelikler (kullanici_id, paket, aylik_kredi, kalan_kredi)
            VALUES (%s, 'ucretsiz', %s, %s)
            """,
            (kullanici["id"], UCRETSIZ_AYLIK_KREDI, UCRETSIZ_AYLIK_KREDI),
        )
    return kullanici


# ------------------------------------------------------------------- READ
def getir(conn, kullanici_id):
    """id ile tek kullanıcı döndürür; yoksa None."""
    return conn.execute(
        "SELECT * FROM kullanicilar WHERE id = %s", (kullanici_id,)
    ).fetchone()


def email_ile_getir(conn, email):
    """E-posta ile kullanıcıyı ve abonelik bilgisini (JOIN ile) döndürür; yoksa None."""
    return conn.execute(
        """
        SELECT k.id, k.ad_soyad, k.email, k.rol, a.paket, a.kalan_kredi
        FROM kullanicilar k
        LEFT JOIN abonelikler a ON a.kullanici_id = k.id
        WHERE k.email = %s
        """,
        (email,),
    ).fetchone()


def listele(conn, limit=50, offset=0):
    """
    Kullanıcıları sayfa sayfa listeler.
    LIMIT  -> en fazla kaç satır gelsin
    OFFSET -> baştan kaç satır atlansın (2. sayfa için offset=50)
    """
    return conn.execute(
        """
        SELECT id, ad_soyad, email, rol, yetki, olusturma_tarihi, son_giris
        FROM kullanicilar ORDER BY id LIMIT %s OFFSET %s
        """,
        (limit, offset),
    ).fetchall()


# ----------------------------------------------------------------- UPDATE
def guncelle(conn, kullanici_id, ad_soyad=None, rol=None):
    """
    Verilen alanları günceller; verilmeyenler (None) aynı kalır.
    COALESCE(%s, ad_soyad) -> yeni değer NULL ise eski değeri koru.
    Güncellenen satırı döndürür; kullanıcı yoksa None.
    """
    return conn.execute(
        """
        UPDATE kullanicilar
        SET ad_soyad = COALESCE(%s, ad_soyad),
            rol      = COALESCE(%s, rol)
        WHERE id = %s
        RETURNING *
        """,
        (ad_soyad, rol, kullanici_id),
    ).fetchone()


def kredi_dus(conn, kullanici_id, miktar=1):
    """
    Kullanıcının kalan kredisinden düşer. Kredi yetmezse CHECK kısıtı
    (kalan_kredi BETWEEN 0 AND aylik_kredi) hata verir ve işlem yapılmaz.
    """
    return conn.execute(
        """
        UPDATE abonelikler SET kalan_kredi = kalan_kredi - %s
        WHERE kullanici_id = %s
        RETURNING kalan_kredi
        """,
        (miktar, kullanici_id),
    ).fetchone()


# ----------------------------------------------------------------- DELETE
def sil(conn, kullanici_id):
    """
    Kullanıcıyı siler. ON DELETE CASCADE sayesinde aboneliği, belgeleri ve
    onların çıkarım kayıtları da otomatik silinir.
    Silindiyse True, böyle bir kullanıcı yoksa False döndürür.
    rowcount -> komuttan etkilenen satır sayısı.
    """
    sonuc = conn.execute("DELETE FROM kullanicilar WHERE id = %s", (kullanici_id,))
    return sonuc.rowcount == 1
