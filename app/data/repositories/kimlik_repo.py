"""
kimlik_repo.py - Giriş, kilitleme, çıkış ve yetki ile ilgili SQL sorguları (Hafta 5).

Tablolar: kullanicilar (yetki, basarisiz_giris, kilit_bitis, son_giris, token_surumu)
          giris_denemeleri (güvenlik günlüğü)
"""


def giris_icin_getir(conn, email):
    """
    Girişte gereken bilgileri getirir (parola hash'i ve kilit durumu dahil).
    kilitli_mi -> kilit_bitis şu andan ilerideyse TRUE (hesap hâlâ kilitli).
    Bu fonksiyonun sonucu ASLA olduğu gibi frontend'e gönderilmez (hash içerir).
    """
    return conn.execute(
        """
        SELECT id, ad_soyad, email, rol, yetki, sifre_hash, token_surumu,
               basarisiz_giris, kilit_bitis,
               (kilit_bitis IS NOT NULL AND kilit_bitis > now()) AS kilitli_mi
        FROM kullanicilar
        WHERE email = %s
        """,
        (email,),
    ).fetchone()


def oturum_icin_getir(conn, kullanici_id):
    """
    Token ile gelen her istekte kullanıcıyı veritabanından tekrar okur.
    Böylece kullanıcı silinmişse, yetkisi değişmişse veya çıkış yapmışsa
    (token_surumu artmışsa) eski token işe yaramaz.
    """
    return conn.execute(
        """
        SELECT k.id, k.ad_soyad, k.email, k.rol, k.yetki, k.token_surumu,
               k.son_giris, a.paket, a.kalan_kredi
        FROM kullanicilar k
        LEFT JOIN abonelikler a ON a.kullanici_id = k.id
        WHERE k.id = %s
        """,
        (kullanici_id,),
    ).fetchone()


def basarisiz_giris_kaydet(conn, kullanici_id, en_fazla_deneme, kilit_dakika):
    """
    Hatalı parola sayacını 1 artırır. Sayaç sınıra ulaşırsa hesabı kilitler.

    Parametreler:
        en_fazla_deneme -> kaçıncı hatada kilitlensin (ör. 5)
        kilit_dakika    -> kaç dakika kilitli kalsın (ör. 15)

    CASE WHEN ... THEN ... ELSE ... END -> SQL'deki "eğer" yapısı.
    make_interval(mins => 15) -> "15 dakika" süresini üretir.
    Kilit kurulduğunda sayaç 0'a döner (kilit bitince 5 yeni hak).
    """
    return conn.execute(
        """
        UPDATE kullanicilar
        SET kilit_bitis = CASE WHEN basarisiz_giris + 1 >= %(sinir)s
                               THEN now() + make_interval(mins => %(dakika)s)
                               ELSE kilit_bitis END,
            basarisiz_giris = CASE WHEN basarisiz_giris + 1 >= %(sinir)s
                                   THEN 0 ELSE basarisiz_giris + 1 END
        WHERE id = %(id)s
        RETURNING basarisiz_giris, kilit_bitis,
                  (kilit_bitis IS NOT NULL AND kilit_bitis > now()) AS kilitli_mi
        """,
        {"sinir": en_fazla_deneme, "dakika": kilit_dakika, "id": kullanici_id},
    ).fetchone()


def basarili_giris_kaydet(conn, kullanici_id):
    """Başarılı girişte sayacı ve kilidi sıfırlar, son giriş zamanını yazar."""
    conn.execute(
        """
        UPDATE kullanicilar
        SET basarisiz_giris = 0, kilit_bitis = NULL, son_giris = now()
        WHERE id = %s
        """,
        (kullanici_id,),
    )


def token_surumunu_artir(conn, kullanici_id):
    """Çıkışta çağrılır: kullanıcının daha önce aldığı TÜM token'lar geçersiz olur."""
    conn.execute(
        "UPDATE kullanicilar SET token_surumu = token_surumu + 1 WHERE id = %s",
        (kullanici_id,),
    )


def yetki_ver(conn, email, yetki):
    """
    Kullanıcının yetkisini değiştirir ('kullanici' / 'yonetici').
    Yetki değişince token_surumu da artar: eski yetkiyle alınmış token'lar geçersiz olur.
    Döndürür: güncellenen satır; böyle e-posta yoksa None.
    """
    return conn.execute(
        """
        UPDATE kullanicilar SET yetki = %s, token_surumu = token_surumu + 1
        WHERE email = %s
        RETURNING id, email, yetki
        """,
        (yetki, email),
    ).fetchone()


def giris_denemesi_kaydet(conn, email, basarili, ip_adresi):
    """Her giriş denemesini günlüğe yazar (parola YAZILMAZ)."""
    conn.execute(
        "INSERT INTO giris_denemeleri (email, basarili, ip_adresi) VALUES (%s, %s, %s)",
        (email, basarili, ip_adresi),
    )


def son_denemeler(conn, limit=20):
    """Yönetici paneli için son giriş denemeleri (en yeni en üstte)."""
    return conn.execute(
        """
        SELECT email, basarili, ip_adresi, tarih
        FROM giris_denemeleri ORDER BY tarih DESC LIMIT %s
        """,
        (limit,),
    ).fetchall()
