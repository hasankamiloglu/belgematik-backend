-- =====================================================================
-- MIGRATION 005: Alan eşleme ve doğrulama (Hafta 7)
-- =====================================================================
-- Hafta 4'te şema, şema alanı ve çıkarım tabloları kurulmuştu. Bu dosya
-- alan eşleme ve doğrulama için gereken ek bilgileri ekler.
-- =====================================================================


-- 1) ANAHTAR KELİMELER: Alan eşleyicinin, OCR metninde hangi satırda bu alanı
--    arayacağını söyler. Virgülle ayrılır; "-" ile başlayan kelime o satırı ELER.
--    Örnek toplam_tutar:  "GENEL TOPLAM,TOPLAM,TUTAR,-ARA,-KDV"
--      -> "TOPLAM" geçen satırı ara, ama "ARA TOPLAM" ve "TOPKDV" satırlarını alma.
--    Kullanıcı kendi şemasını tanımlarken bu kelimeleri kendisi yazar.
ALTER TABLE sema_alanlari ADD COLUMN anahtar_kelimeler VARCHAR(255);

-- 2) Alanların ekrandaki sırası (kullanıcı şemalarında girildiği sıra)
ALTER TABLE sema_alanlari ADD COLUMN sira SMALLINT NOT NULL DEFAULT 0;

-- 3) Her alanın doğrulama sonucu mesajı. gecerli_mi = false ise NEDEN geçersiz?
--    Örnek: "Vergi numarasının kontrol hanesi tutmuyor."
ALTER TABLE cikarim_degerleri ADD COLUMN hata_mesaji VARCHAR(255);

-- 4) Alanlar ARASI iş kuralı sonuçları (ör. "KDV + matrah = toplam").
--    Tek bir alana ait olmadıkları için çıkarım kaydında JSON listesi olarak tutulur:
--    [{"kural": "...", "gecerli": true/false, "mesaj": "..."}]
ALTER TABLE cikarim_kayitlari
    ADD COLUMN kural_sonuclari JSONB NOT NULL DEFAULT '[]';

-- 5) Çıkarımı başlatan kullanıcı (belge sahibi). Sorgularda sahiplik kontrolü için.
ALTER TABLE cikarim_kayitlari
    ADD COLUMN kullanici_id INTEGER REFERENCES kullanicilar(id) ON DELETE CASCADE;

-- 6) Vergi no kuralı: 10 hane (şirket VKN) VEYA 11 hane (şahıs şirketi TCKN)
UPDATE sema_alanlari SET dogrulama_kurali = '^[0-9]{10,11}$' WHERE alan_adi = 'vergi_no';

-- 7) Var olan sistem şemalarının alanlarına anahtar kelimeleri yaz
--    (Örnek veri yeniden yüklenmese bile eşleme çalışsın diye)
UPDATE sema_alanlari sa SET anahtar_kelimeler = k.kelimeler
FROM (VALUES
    ('vergi_no',     'VKN,V.K.N,VERGI NO,VERGI NUMARASI,V.D,VD,TCKN'),
    ('tarih',        'TARIH,TARİH,TAR'),
    ('fis_no',       'FIS NO,FİŞ NO,FIS,FİŞ,BELGE NO'),
    ('fatura_no',    'FATURA NO,FATURA NUMARASI,FATURA'),
    ('kdv_orani',    'KDV %,KDV,%'),
    ('kdv_tutari',   'TOPKDV,TOPLAM KDV,KDV TUTARI,HESAPLANAN KDV,KDV,-MATRAH,-HARIC'),
    ('matrah',       'MATRAH,KDV HARIC,ARA TOPLAM'),
    ('toplam_tutar', 'GENEL TOPLAM,ODENECEK TUTAR,TOPLAM,TUTAR,-ARA,-KDV,-MATRAH'),
    ('telefon',      'TEL,TELEFON,GSM,CEP,MOBIL'),
    ('email',        'E-POSTA,EPOSTA,E-MAIL,EMAIL,MAIL')
) AS k(alan_adi, kelimeler)
WHERE sa.alan_adi = k.alan_adi;
