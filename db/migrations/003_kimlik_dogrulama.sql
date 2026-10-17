-- =====================================================================
-- MIGRATION 003: Kimlik doğrulama ve yetkilendirme (Hafta 5)
-- =====================================================================
-- Hafta 4'te kullanicilar tablosunda "sifre_hash" kolonu zaten vardı.
-- Bu dosya giriş/yetki için gereken EK kolonları ve giriş kayıt tablosunu ekler.
--
-- ALTER TABLE -> var olan tabloyu değiştirir (içindeki veri silinmez).
--
-- İKİ FARKLI KAVRAM (karıştırılmamalı):
--   rol   -> Hesap TÜRÜ: bireysel / kobi / muhasebeci (paket ve kredi için)
--   yetki -> Erişim SEVİYESİ: kullanici / yonetici (hangi sayfalara girebilir)
-- =====================================================================


-- Erişim seviyesi. Kayıt olan herkes "kullanici" olarak başlar.
-- Yönetici yapmak SADECE sunucudan mümkündür: python manage.py yonetici EMAIL
ALTER TABLE kullanicilar
    ADD COLUMN yetki VARCHAR(20) NOT NULL DEFAULT 'kullanici'
        CONSTRAINT chk_yetki CHECK (yetki IN ('kullanici', 'yonetici'));

-- Art arda yapılan başarısız giriş sayısı. Başarılı girişte 0'a döner.
ALTER TABLE kullanicilar
    ADD COLUMN basarisiz_giris SMALLINT NOT NULL DEFAULT 0
        CONSTRAINT chk_basarisiz_giris CHECK (basarisiz_giris >= 0);

-- Hesap bu zamana kadar kilitli (5 hatalı denemeden sonra 15 dakika). NULL = kilitli değil.
ALTER TABLE kullanicilar ADD COLUMN kilit_bitis TIMESTAMPTZ;

-- Son başarılı giriş zamanı (kullanıcıya "son girişiniz" diye gösterilebilir).
ALTER TABLE kullanicilar ADD COLUMN son_giris TIMESTAMPTZ;

-- Token sürümü: kullanıcı "Çıkış" yapınca 1 artar. Token içinde bu sayı da
-- yazılıdır; sayılar tutmazsa token GEÇERSİZ sayılır. Böylece çıkış yapınca
-- eski token çalınmış olsa bile bir daha kullanılamaz.
ALTER TABLE kullanicilar
    ADD COLUMN token_surumu INTEGER NOT NULL DEFAULT 0;


-- ---------------------------------------------------------------------
-- GİRİŞ DENEMELERİ: her giriş denemesinin kaydı (güvenlik günlüğü / log)
-- ---------------------------------------------------------------------
-- Kullanıcıya bağlı DEĞİL (FK yok): olmayan bir e-postayla yapılan denemeler de
-- kaydedilir. Böylece saldırı girişimleri sonradan incelenebilir.
-- Parola ASLA kaydedilmez, sadece e-posta, sonuç ve IP.
CREATE TABLE giris_denemeleri (
    id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email     VARCHAR(255) NOT NULL,
    basarili  BOOLEAN      NOT NULL,
    ip_adresi VARCHAR(45),                      -- 45 karakter: IPv6 adresi sığsın
    tarih     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- "Bu e-postaya son denemeler" sorgusu için bileşik indeks
CREATE INDEX idx_giris_denemeleri_email_tarih ON giris_denemeleri (email, tarih DESC);
