-- =====================================================================
-- MIGRATION 004: Fotoğraf yükleme ve ön işleme (Hafta 6)
-- =====================================================================
-- belgeler tablosu Hafta 4'te oluşturuldu. Ön işleme sonuçlarını saklamak
-- için yeni kolonlar ve yeni bir durum ('on_islendi') ekleniyor.
--
-- Belgenin yaşam döngüsü (durum):
--   yuklendi   -> dosya kaydedildi (PDF'ler şimdilik bu durumda kalır)
--   on_islendi -> görsel düzeltildi, OCR'a hazır          (Hafta 6)
--   islendi    -> OCR + alan çıkarma yapıldı               (sonraki haftalar)
--   hatali     -> işlenemedi
-- =====================================================================


-- 1) Durum listesine 'on_islendi' ekle.
--    CHECK kısıtı değiştirilemez; eskisi silinip yenisi eklenir.
--    "belgeler_durum_check" -> 001'de isim vermediğimiz için PostgreSQL'in verdiği ad.
ALTER TABLE belgeler DROP CONSTRAINT belgeler_durum_check;
ALTER TABLE belgeler ADD CONSTRAINT chk_belge_durum
    CHECK (durum IN ('yuklendi', 'on_islendi', 'islendi', 'hatali'));


-- 2) Ön işleme bilgileri
ALTER TABLE belgeler
    -- Dosyanın SHA-256 parmak izi (64 karakter). Aynı dosya iki kez yüklenmesin diye.
    ADD COLUMN dosya_hash      CHAR(64),
    -- Ön işlenmiş (gri, döndürülmüş, kontrastı açılmış) görselin yolu. PDF'te NULL.
    ADD COLUMN islenmis_yol    VARCHAR(500),
    -- Listede gösterilecek küçük önizleme görselinin yolu
    ADD COLUMN kucuk_yol       VARCHAR(500),
    -- Orijinal görselin boyutu (piksel)
    ADD COLUMN genislik        INTEGER CONSTRAINT chk_genislik  CHECK (genislik > 0),
    ADD COLUMN yukseklik       INTEGER CONSTRAINT chk_yukseklik CHECK (yukseklik > 0),
    -- 0-100 arası kalite puanı (bulanıklık, karanlık, kontrast ölçümünden)
    ADD COLUMN kalite_puani    SMALLINT CONSTRAINT chk_kalite CHECK (kalite_puani BETWEEN 0 AND 100),
    -- Kalite uyarıları listesi, ör. ["Görsel bulanık görünüyor."]
    -- JSONB -> JSON verisini saklayan PostgreSQL tipi
    ADD COLUMN kalite_uyarilari JSONB NOT NULL DEFAULT '[]';


-- 3) İŞ KURALI: Bir kullanıcı AYNI dosyayı iki kez yükleyemez.
--    (Aynı fişi iki kez işleyip iki kez kredi harcamasın, muhasebede çift kayıt olmasın.)
--    Farklı kullanıcılar aynı dosyayı yükleyebilir; kural kullanıcı bazlıdır.
--    Eski örnek verilerde dosya_hash NULL'dır; NULL'lar birbirine eşit sayılmaz, sorun olmaz.
ALTER TABLE belgeler
    ADD CONSTRAINT uq_belge_kullanici_hash UNIQUE (kullanici_id, dosya_hash);
