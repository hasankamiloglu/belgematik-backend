-- =====================================================================
-- MIGRATION 007: Yapay zekâ ile yapılandırılmış veri çıkarımı (Hafta 10)
-- =====================================================================
-- Hafta 7'de alanlar KURAL TABANLI eşleyiciyle (anahtar kelime / kalıp / konum)
-- bulunuyordu. Bu hafta ikinci bir yöntem eklendi: belge görseli bir yapay zekâ
-- modeline (Gemini) gönderilir, model alanları JSON olarak döndürür, biz de bu
-- çıktıyı kendi kurallarımızla doğrularız.
--
-- ŞEFFAFLIK: Hangi yöntem, hangi model ve hangi istem (prompt) sürümü kullanıldı,
-- modelin HAM çıktısı neydi? Hepsi kaydedilir; sonradan "yapay zekâ ne demişti?"
-- sorusu cevaplanabilir.
-- =====================================================================


-- 1) ÇIKARIM KAYDI: yöntem ve yapay zekâ bilgileri
ALTER TABLE cikarim_kayitlari
    ADD COLUMN cikarim_yontemi VARCHAR(15) NOT NULL DEFAULT 'kural'
        CONSTRAINT chk_cikarim_yontemi CHECK (cikarim_yontemi IN ('kural', 'yapay_zeka')),
    ADD COLUMN ai_model       VARCHAR(60),   -- ör. gemini-flash-latest
    ADD COLUMN istem_surumu   VARCHAR(20),   -- ör. v1 (istem değişince sürüm artar)
    ADD COLUMN ai_ham_cikti   JSONB,         -- modelin döndürdüğü JSON (olduğu gibi)
    ADD COLUMN ai_notu        VARCHAR(300);  -- ör. "Yapay zekâ kullanılamadı; kural tabanlı eşleme kullanıldı."


-- 2) ALAN DEĞERLERİ: düşük güven işareti ve alan notu
--    dusuk_guven = true -> değer bulundu ama güveni eşiğin altında; kullanıcı kontrol etmeli.
--    kaynak_notu        -> ör. "Değer OCR metninde doğrulanamadı (yapay zekâ uydurmuş olabilir)."
ALTER TABLE cikarim_degerleri
    ADD COLUMN dusuk_guven BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN kaynak_notu VARCHAR(255);


-- 3) API ÇAĞRI GÜNLÜĞÜ: yapay zekâya özgü iki hata türü eklenir
--    guvenlik -> model güvenlik filtresi yüzünden cevap vermedi
--    cikti    -> model cevap verdi ama çıktı geçersiz (JSON değil, şemaya uymuyor)
ALTER TABLE api_cagrilari DROP CONSTRAINT IF EXISTS api_cagrilari_hata_turu_check;
ALTER TABLE api_cagrilari
    ADD CONSTRAINT chk_api_hata_turu CHECK (hata_turu IN (
        'anahtar_yok', 'kimlik', 'hiz_siniri', 'zaman_asimi', 'baglanti',
        'sunucu', 'yanit', 'dosya', 'guvenlik', 'cikti'));
