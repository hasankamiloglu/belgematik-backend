"""
cikarim_repo.py - cikarim_kayitlari ve cikarim_degerleri (N-N ara tablosu) için CRUD.

N-N ilişki hatırlatma:
    Bir çıkarım kaydında ÇOK alan vardır (firma_adi, tarih, toplam_tutar...).
    Bir şema alanı da ÇOK çıkarım kaydında kullanılır.
    Bu ilişkiyi cikarim_degerleri ara tablosu kurar: (cikarim_id, alan_id, deger).

Hafta 7: sonuc_kaydet, son_cikarim, alan_degerleri eklendi (OCR + eşleme + doğrulama sonucu).
"""

import json


def kaydet(conn, belge_id, sema_adi, ocr_motoru, ham_metin, guven_skoru, degerler):
    """
    Bir çıkarım kaydını ve tüm alan değerlerini TEK TRANSACTION içinde kaydeder.

    Parametreler:
        sema_adi -> sistem şemasının adı ('fis', 'fatura', 'kartvizit')
        degerler -> {"firma_adi": "...", "toplam_tutar": "247.50", ...}

    Değerlerden biri hatalıysa (ör. şemada olmayan bir alan) HİÇBİR şey kaydedilmez;
    yarım kalmış, değerleri eksik bir çıkarım kaydı oluşmaz.
    """
    with conn.transaction():
        kayit = conn.execute(
            """
            INSERT INTO cikarim_kayitlari (belge_id, sema_id, ocr_motoru, ham_metin, guven_skoru)
            SELECT %s, id, %s, %s, %s
            FROM semalar
            WHERE ad = %s AND sistem_semasi_mi
            RETURNING *
            """,
            (belge_id, ocr_motoru, ham_metin, guven_skoru, sema_adi),
        ).fetchone()
        if kayit is None:
            raise ValueError(f"'{sema_adi}' adında bir sistem şeması yok")

        for alan_adi, deger in degerler.items():
            eklenen = conn.execute(
                """
                INSERT INTO cikarim_degerleri (cikarim_id, alan_id, deger)
                SELECT %s, id, %s
                FROM sema_alanlari
                WHERE sema_id = %s AND alan_adi = %s
                RETURNING id
                """,
                (kayit["id"], deger, kayit["sema_id"], alan_adi),
            ).fetchone()
            if eklenen is None:
                # raise -> transaction bloğundan hata ile çıkılır, her şey geri alınır
                raise ValueError(f"'{sema_adi}' şemasında '{alan_adi}' alanı yok")

    return kayit


def degerleri_getir(conn, cikarim_id):
    """
    Bir çıkarım kaydının tüm alanlarını ve değerlerini döndürür.
    JOIN ile ara tablodaki alan_id, sema_alanlari tablosundaki alan adına çevrilir.
    """
    return conn.execute(
        """
        SELECT sa.alan_adi, cd.deger, cd.gecerli_mi, cd.duzeltildi_mi
        FROM cikarim_degerleri cd
        JOIN sema_alanlari sa ON sa.id = cd.alan_id
        WHERE cd.cikarim_id = %s
        ORDER BY sa.id
        """,
        (cikarim_id,),
    ).fetchall()


def bekleyenleri_listele(conn, limit=20):
    """Doğrulama bekleyen çıkarımlar (kısmi indeks: idx_cikarim_kayitlari_bekleyen)."""
    return conn.execute(
        """
        SELECT id, belge_id, guven_skoru, olusturma_tarihi
        FROM cikarim_kayitlari
        WHERE durum = 'bekliyor'
        ORDER BY olusturma_tarihi
        LIMIT %s
        """,
        (limit,),
    ).fetchall()


def deger_duzelt(conn, cikarim_id, alan_adi, yeni_deger):
    """
    Kullanıcının düzeltme ekranında bir değeri değiştirmesi.
    Değer güncellenir, 'duzeltildi_mi' işaretlenir ve çıkarım kaydının
    durumu 'duzeltildi' yapılır. İki UPDATE tek transaction içindedir.
    """
    with conn.transaction():
        satir = conn.execute(
            """
            UPDATE cikarim_degerleri cd
            SET deger = %s, duzeltildi_mi = true, gecerli_mi = true
            FROM sema_alanlari sa
            WHERE sa.id = cd.alan_id
              AND cd.cikarim_id = %s
              AND sa.alan_adi = %s
            RETURNING cd.id, sa.alan_adi, cd.deger, cd.duzeltildi_mi
            """,
            (yeni_deger, cikarim_id, alan_adi),
        ).fetchone()
        if satir is not None:
            conn.execute(
                "UPDATE cikarim_kayitlari SET durum = 'duzeltildi' WHERE id = %s",
                (cikarim_id,),
            )
    return satir


def sil(conn, cikarim_id):
    """Çıkarım kaydını siler; değerleri CASCADE ile silinir. True/False döndürür."""
    return conn.execute(
        "DELETE FROM cikarim_kayitlari WHERE id = %s", (cikarim_id,)
    ).rowcount == 1


# ================================================== Hafta 7: OCR + eşleme sonucu
def sonuc_kaydet(conn, belge_id, kullanici_id, sema_id, ocr, durum, kural_sonuclari, degerler):
    """
    Bir belgenin işlenme sonucunu TEK TRANSACTION ile kaydeder:
        1) cikarim_kayitlari  -> 1 satır (OCR metni, güven, durum, iş kuralı sonuçları)
        2) cikarim_degerleri  -> her alan için 1 satır (değer, güven, geçerli mi, hata mesajı)
        3) belgeler.durum     -> 'islendi'
    Biri başarısız olursa hiçbiri kaydedilmez.

    Parametreler:
        ocr      -> {"metin", "guven", "motor"}
        degerler -> [{"alan_id", "deger", "guven", "gecerli_mi", "hata_mesaji"}, ...]
    """
    with conn.transaction():
        kayit = conn.execute(
            """
            INSERT INTO cikarim_kayitlari (belge_id, kullanici_id, sema_id, ocr_motoru,
                                           ham_metin, guven_skoru, durum, kural_sonuclari)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, olusturma_tarihi
            """,
            (belge_id, kullanici_id, sema_id, ocr["motor"], ocr["metin"], ocr["guven"],
             durum, json.dumps(kural_sonuclari, ensure_ascii=False)),
        ).fetchone()
        for d in degerler:
            conn.execute(
                """
                INSERT INTO cikarim_degerleri (cikarim_id, alan_id, deger, guven_skoru,
                                               gecerli_mi, hata_mesaji)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (kayit["id"], d["alan_id"], d["deger"], d["guven"], d["gecerli_mi"], d["hata_mesaji"]),
            )
        conn.execute("UPDATE belgeler SET durum = 'islendi' WHERE id = %s", (belge_id,))
    return kayit


def son_cikarim(conn, belge_id, kullanici_id):
    """
    Belgenin EN SON çıkarım kaydı (sahiplik kontrolüyle: sadece belgenin sahibi).
    Bir belge farklı şemalarla birkaç kez işlenebilir; ekranda en sonuncusu gösterilir.
    """
    return conn.execute(
        """
        SELECT ck.id, ck.belge_id, ck.sema_id, s.ad AS sema_adi, ck.ocr_motoru, ck.ham_metin,
               ck.guven_skoru, ck.durum, ck.kural_sonuclari, ck.olusturma_tarihi
        FROM cikarim_kayitlari ck
        JOIN belgeler b ON b.id = ck.belge_id
        JOIN semalar  s ON s.id = ck.sema_id
        WHERE ck.belge_id = %s AND b.kullanici_id = %s
        ORDER BY ck.id DESC
        LIMIT 1
        """,
        (belge_id, kullanici_id),
    ).fetchone()


def alan_degerleri(conn, cikarim_id):
    """Bir çıkarımın tüm alanları: şema bilgisi + bulunan değer + doğrulama sonucu."""
    return conn.execute(
        """
        SELECT sa.alan_adi, sa.veri_tipi, sa.zorunlu_mu, cd.deger, cd.guven_skoru,
               cd.gecerli_mi, cd.hata_mesaji, cd.duzeltildi_mi
        FROM cikarim_degerleri cd
        JOIN sema_alanlari sa ON sa.id = cd.alan_id
        WHERE cd.cikarim_id = %s
        ORDER BY sa.sira, sa.id
        """,
        (cikarim_id,),
    ).fetchall()
