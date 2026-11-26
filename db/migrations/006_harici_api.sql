-- =====================================================================
-- MIGRATION 006: Harici OCR API entegrasyonu (Hafta 9)
-- =====================================================================
-- Hafta 7'de OCR sadece bilgisayardaki Tesseract ile yapılıyordu. Bu hafta
-- dış bir OCR servisi (OCR.space) eklendi. Bu dosya:
--   1) Çıkarım kaydında yeni motor adına ('ocr_space') izin verir,
--   2) "API çalışmadı, Tesseract ile okundu" gibi notları saklar,
--   3) Her API çağrısını (başarılı / hatalı) günlüğe yazmak için tablo kurar.
-- =====================================================================


-- 1) OCR MOTORU: CHECK kısıtı değiştirilemez; eskisi silinip yenisi eklenir.
--    Hafta 4'teki kısıt sadece 'tesseract' ve 'yapay_zeka' değerlerine izin veriyordu.
ALTER TABLE cikarim_kayitlari DROP CONSTRAINT IF EXISTS cikarim_kayitlari_ocr_motoru_check;
ALTER TABLE cikarim_kayitlari
    ADD CONSTRAINT chk_ocr_motoru CHECK (ocr_motoru IN ('tesseract', 'ocr_space', 'yapay_zeka'));


-- 2) OCR NOTU: Harici API hata verip yedek motora (Tesseract) geçildiyse nedeni.
--    Örnek: "Harici OCR kullanılamadı (zaman aşımı); Tesseract ile okundu."
--    Her şey yolundaysa NULL kalır.
ALTER TABLE cikarim_kayitlari ADD COLUMN ocr_notu VARCHAR(300);


-- 3) API ÇAĞRI GÜNLÜĞÜ: Dış servise yapılan her çağrının kaydı.
--    Neden? Hız sınırına ne kadar yaklaştığımızı, hangi hataların sık olduğunu ve
--    servisin ne kadar sürede cevap verdiğini yönetici panelinden görmek için.
--    API anahtarı bu tabloya ASLA yazılmaz.
CREATE TABLE api_cagrilari (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- Kullanıcı veya belge silinirse günlük kaydı kalır, sadece bağlantı boşalır
    kullanici_id   INTEGER REFERENCES kullanicilar(id) ON DELETE SET NULL,
    belge_id       INTEGER REFERENCES belgeler(id)     ON DELETE SET NULL,
    servis         VARCHAR(30) NOT NULL,                 -- 'ocr_space'
    durum          VARCHAR(10) NOT NULL CHECK (durum IN ('basarili', 'hata')),
    -- Hata türü (sadece durum = 'hata' iken dolu)
    hata_turu      VARCHAR(20) CHECK (hata_turu IN ('anahtar_yok', 'kimlik', 'hiz_siniri',
                                                    'zaman_asimi', 'baglanti', 'sunucu',
                                                    'yanit', 'dosya')),
    http_kodu      SMALLINT,                             -- 200, 403, 429, 500 ... (yoksa NULL)
    deneme_sayisi  SMALLINT NOT NULL DEFAULT 1 CHECK (deneme_sayisi >= 1),
    sure_ms        INTEGER CHECK (sure_ms >= 0),         -- toplam süre (milisaniye)
    hata_mesaji    VARCHAR(300),
    tarih          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Başarılı çağrının hata türü olamaz; hatalı çağrının olmalı
    CONSTRAINT chk_hata_turu_durum CHECK (
        (durum = 'basarili' AND hata_turu IS NULL) OR
        (durum = 'hata'     AND hata_turu IS NOT NULL)
    )
);

-- Yönetici paneli en yeni çağrıları gösterir -> tarihe göre indeks
CREATE INDEX idx_api_cagrilari_tarih ON api_cagrilari (tarih DESC);
