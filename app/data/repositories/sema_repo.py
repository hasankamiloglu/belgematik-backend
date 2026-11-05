"""
sema_repo.py - semalar ve sema_alanlari tabloları için SQL sorguları (Hafta 7).

Şema = bir belge türünün "kalıbı": hangi alanlar var, tipleri ne, zorunlu mu, nasıl doğrulanır.
    Sistem şemaları  -> herkes kullanır (fis, fatura, kartvizit), kullanici_id NULL
    Kullanıcı şeması -> sadece sahibi görür ve kullanır (ör. muhasebecinin "gider_pusulasi")
"""

ALAN_KOLONLARI = "id, alan_adi, veri_tipi, zorunlu_mu, dogrulama_kurali, anahtar_kelimeler, sira"


def listele(conn, kullanici_id):
    """
    Kullanıcının KULLANABİLECEĞİ şemalar: sistem şemaları + kendi şemaları.
    Başka kullanıcıların şemaları listede YOKTUR (sahiplik kontrolü).
    """
    return conn.execute(
        """
        SELECT id, ad, aciklama, sistem_semasi_mi
        FROM semalar
        WHERE sistem_semasi_mi OR kullanici_id = %s
        ORDER BY sistem_semasi_mi DESC, id
        """,
        (kullanici_id,),
    ).fetchall()


def alanlari_getir(conn, sema_id):
    """Bir şemanın alanları (ekranda girildiği sırayla)."""
    return conn.execute(
        f"SELECT {ALAN_KOLONLARI} FROM sema_alanlari WHERE sema_id = %s ORDER BY sira, id",
        (sema_id,),
    ).fetchall()


def kullanilabilir_getir(conn, sema_id, kullanici_id):
    """
    Şemayı getirir AMA sadece sistem şemasıysa veya kullanıcının kendisininse.
    Başkasının şeması istenirse None döner (API 404 verir).
    """
    return conn.execute(
        """
        SELECT id, ad, aciklama, sistem_semasi_mi, kullanici_id
        FROM semalar
        WHERE id = %s AND (sistem_semasi_mi OR kullanici_id = %s)
        """,
        (sema_id, kullanici_id),
    ).fetchone()


def olustur(conn, kullanici_id, ad, aciklama, alanlar):
    """
    Kullanıcı şeması ve alanlarını TEK TRANSACTION ile ekler.
    Alanlardan biri hatalıysa (ör. aynı ad iki kez) şema da eklenmez.

    alanlar -> [{"alan_adi", "veri_tipi", "zorunlu_mu", "dogrulama_kurali", "anahtar_kelimeler"}]
    """
    with conn.transaction():
        sema = conn.execute(
            """
            INSERT INTO semalar (kullanici_id, ad, aciklama, sistem_semasi_mi)
            VALUES (%s, %s, %s, false)
            RETURNING id, ad, aciklama, sistem_semasi_mi
            """,
            (kullanici_id, ad, aciklama),
        ).fetchone()
        for sira, alan in enumerate(alanlar, start=1):
            conn.execute(
                """
                INSERT INTO sema_alanlari (sema_id, alan_adi, veri_tipi, zorunlu_mu,
                                           dogrulama_kurali, anahtar_kelimeler, sira)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (sema["id"], alan["alan_adi"], alan["veri_tipi"], alan["zorunlu_mu"],
                 alan.get("dogrulama_kurali"), alan.get("anahtar_kelimeler"), sira),
            )
    return sema


def sil(conn, sema_id, kullanici_id):
    """
    Kullanıcının KENDİ şemasını siler (sistem şeması silinemez: kullanici_id NULL'dır).
    Şema bir çıkarımda kullanıldıysa ON DELETE RESTRICT yüzünden PostgreSQL
    RestrictViolation hatası verir; servis bunu "kullanımda" mesajına çevirir.
    Döndürür: silindiyse True.
    """
    return conn.execute(
        "DELETE FROM semalar WHERE id = %s AND kullanici_id = %s AND NOT sistem_semasi_mi",
        (sema_id, kullanici_id),
    ).rowcount == 1
