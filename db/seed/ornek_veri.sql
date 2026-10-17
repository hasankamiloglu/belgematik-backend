-- =====================================================================
-- ÖRNEK (SENTETİK) VERİ
-- =====================================================================
-- Bu veriler TAMAMEN UYDURMADIR. Gerçek kişi, gerçek e-posta, gerçek vergi
-- numarası veya gerçek şirket İÇERMEZ. Bu sayede KVKK (Kişisel Verilerin
-- Korunması Kanunu) açısından sorun oluşturmaz.
--   - E-postalar "@ornek.test" ile biter (.test alan adı gerçekte hiç kullanılmaz)
--   - Firma adlarının sonunda "(Örnek)" yazar
--   - Vergi numaraları gerçek bir firmaya ait değildir
--
-- Bu dosya DML (Data Manipulation Language / Veri İşleme Dili) içerir:
--   INSERT -> satır ekler,  DELETE / TRUNCATE -> satır siler
--
-- Çalıştırmak için: python manage.py seed
-- Dosya her çalıştırıldığında önce tabloları boşaltır, sonra yeniden doldurur.
-- =====================================================================

-- TRUNCATE -> tablonun tüm satırlarını hızlıca siler.
-- RESTART IDENTITY -> otomatik id sayaçlarını 1'den yeniden başlatır.
-- CASCADE -> bu tablolara bağlı diğer tabloları da boşaltır.
TRUNCATE kullanicilar, semalar, giris_denemeleri RESTART IDENTITY CASCADE;


-- ---------------------------------------------------------------------
-- Kullanıcılar (3 hesap türü + 1 yönetici)
-- ---------------------------------------------------------------------
-- Hafta 5: Parolalar artık GERÇEK hash'tir (app/services/auth/parola.py ile üretildi).
-- Tüm örnek hesapların parolası: Deneme123   (SADECE geliştirme/demo içindir)
-- Dikkat: parolalar aynı olduğu halde TUZ farklı olduğu için hash'ler birbirinden farklıdır.
-- Biçim: pbkdf2_sha256$<tekrar>$<tuz>$<hash>
INSERT INTO kullanicilar (ad_soyad, email, sifre_hash, rol, yetki) VALUES
    ('Deneme Muhasebeci', 'muhasebeci@ornek.test',
     'pbkdf2_sha256$600000$a08ca8d06ba1f150af7b2d49d2bc2332$ac875b5fda8eee2ee2429d8cef3eaa1fc75ba07f933b5ce84028f219681f6fd8',
     'muhasebeci', 'kullanici'),
    ('Deneme Esnaf', 'kobi@ornek.test',
     'pbkdf2_sha256$600000$b34faaff221a8da724303a5508950742$5bfe3bdef939700c62357170b55a675527ced99dc3f04929819671d6f7f9c4a6',
     'kobi', 'kullanici'),
    ('Deneme Kullanici', 'bireysel@ornek.test',
     'pbkdf2_sha256$600000$986c6a2b7028799f7917f4d1e7862852$8a1563da7ad64a8f5c28b9dc05e6e6757539641ee056132cb6986ae1d52153a5',
     'bireysel', 'kullanici'),
    ('Deneme Yonetici', 'yonetici@ornek.test',
     'pbkdf2_sha256$600000$0ab982c6f250a33877a582be92e9cdb6$9f2af3dcbaf54a756ac7479d0119205a0b675331afd54d68c7d162c3de69fe91',
     'bireysel', 'yonetici');


-- ---------------------------------------------------------------------
-- Abonelikler (her kullanıcıya bir tane -> 1-1)
-- id yerine e-posta ile alt sorgu kullanıyoruz; böylece id'lerin kaç
-- olduğunu bilmemize gerek kalmıyor.
-- ---------------------------------------------------------------------
INSERT INTO abonelikler (kullanici_id, paket, aylik_kredi, kalan_kredi)
SELECT id, 'pro', 500, 430      FROM kullanicilar WHERE email = 'muhasebeci@ornek.test'
UNION ALL
SELECT id, 'ucretsiz', 20, 12   FROM kullanicilar WHERE email = 'kobi@ornek.test'
UNION ALL
SELECT id, 'ucretsiz', 20, 20   FROM kullanicilar WHERE email = 'bireysel@ornek.test'
UNION ALL
SELECT id, 'ucretsiz', 20, 20   FROM kullanicilar WHERE email = 'yonetici@ornek.test';


-- ---------------------------------------------------------------------
-- Sistem şemaları (sahibi yok -> kullanici_id NULL)
-- ---------------------------------------------------------------------
INSERT INTO semalar (kullanici_id, ad, aciklama, sistem_semasi_mi) VALUES
    (NULL, 'fis',       'Market / akaryakıt fişleri',      true),
    (NULL, 'fatura',    'e-Fatura ve kağıt faturalar',      true),
    (NULL, 'kartvizit', 'İş kartları',                      true);

-- Muhasebecinin kendi oluşturduğu özel şema (sahibi var)
INSERT INTO semalar (kullanici_id, ad, aciklama, sistem_semasi_mi)
SELECT id, 'gider_pusulasi', 'Büroya özel gider pusulası şablonu', false
FROM kullanicilar WHERE email = 'muhasebeci@ornek.test';


-- ---------------------------------------------------------------------
-- Şema alanları
-- ---------------------------------------------------------------------
INSERT INTO sema_alanlari (sema_id, alan_adi, veri_tipi, zorunlu_mu, dogrulama_kurali)
SELECT s.id, a.alan_adi, a.veri_tipi, a.zorunlu_mu, a.kural
FROM semalar s
JOIN (VALUES
    ( 1, 'fis', 'firma_adi',     'metin', true,  NULL),
    ( 2, 'fis', 'vergi_no',      'metin', true,  '^[0-9]{10}$'),
    ( 3, 'fis', 'tarih',         'tarih', true,  NULL),
    ( 4, 'fis', 'fis_no',        'metin', false, NULL),
    ( 5, 'fis', 'kdv_orani',     'sayi',  false, NULL),
    ( 6, 'fis', 'kdv_tutari',    'para',  true,  NULL),
    ( 7, 'fis', 'toplam_tutar',  'para',  true,  NULL),
    ( 8, 'fatura', 'firma_adi',    'metin', true,  NULL),
    ( 9, 'fatura', 'vergi_no',     'metin', true,  '^[0-9]{10}$'),
    (10, 'fatura', 'fatura_no',    'metin', true,  NULL),
    (11, 'fatura', 'tarih',        'tarih', true,  NULL),
    (12, 'fatura', 'matrah',       'para',  true,  NULL),
    (13, 'fatura', 'kdv_tutari',   'para',  true,  NULL),
    (14, 'fatura', 'toplam_tutar', 'para',  true,  NULL),
    (15, 'kartvizit', 'ad_soyad', 'metin', true,  NULL),
    (16, 'kartvizit', 'firma',    'metin', false, NULL),
    (17, 'kartvizit', 'telefon',  'metin', false, NULL),
    (18, 'kartvizit', 'email',    'metin', false, NULL)
) AS a(sira, sema_adi, alan_adi, veri_tipi, zorunlu_mu, kural)
    ON s.ad = a.sema_adi AND s.sistem_semasi_mi
-- ORDER BY -> alanlar listedeki sırayla eklensin (id'ler de bu sırayla verilir)
ORDER BY a.sira;


-- ---------------------------------------------------------------------
-- Belgeler
-- ---------------------------------------------------------------------
INSERT INTO belgeler (kullanici_id, dosya_adi, dosya_yolu, dosya_turu, boyut_kb, durum, yuklenme_tarihi)
SELECT k.id, b.dosya_adi, 'uploads/' || b.dosya_adi, b.tur, b.boyut, b.durum, now() - b.once
FROM kullanicilar k
JOIN (VALUES
    ('muhasebeci@ornek.test', 'market_fisi_001.jpg', 'jpg', 812,  'islendi',  interval '3 days'),
    ('muhasebeci@ornek.test', 'akaryakit_fisi.jpg',  'jpg', 640,  'islendi',  interval '2 days'),
    ('muhasebeci@ornek.test', 'fatura_2026_10.pdf',  'pdf', 1530, 'yuklendi', interval '1 hour'),
    ('kobi@ornek.test',       'kirtasiye_fisi.png',  'png', 455,  'islendi',  interval '1 day'),
    ('kobi@ornek.test',       'bulanik_fis.jpg',     'jpg', 390,  'hatali',   interval '5 hours'),
    ('bireysel@ornek.test',   'kartvizit_1.jpg',     'jpg', 220,  'yuklendi', interval '10 minutes')
) AS b(email, dosya_adi, tur, boyut, durum, once) ON k.email = b.email;


-- ---------------------------------------------------------------------
-- Çıkarım kayıtları (işlenmiş belgeler için)
-- ---------------------------------------------------------------------
INSERT INTO cikarim_kayitlari (belge_id, sema_id, ocr_motoru, ham_metin, guven_skoru, durum)
SELECT b.id, s.id, c.motor, c.metin, c.guven, c.durum
FROM belgeler b
JOIN (VALUES
    ('market_fisi_001.jpg', 'tesseract',  'ORNEK MARKET (Ornek) VKN 1111111111 TARIH 12.10.2026 KDV %10 22,50 TOPLAM 247,50', 0.910, 'dogrulandi'),
    ('akaryakit_fisi.jpg',  'yapay_zeka', 'ORNEK AKARYAKIT (Ornek) VKN 2222222222 13.10.2026 KDV 133,33 TOPLAM 800,00',          0.970, 'duzeltildi'),
    ('kirtasiye_fisi.png',  'tesseract',  'ORNEK KIRTASIYE (Ornek) VKN 33333333 14.10.2026 KDV 15,00 TOPLAM 90,00',              0.620, 'bekliyor')
) AS c(dosya_adi, motor, metin, guven, durum) ON b.dosya_adi = c.dosya_adi
JOIN semalar s ON s.ad = 'fis' AND s.sistem_semasi_mi;


-- ---------------------------------------------------------------------
-- Çıkarım değerleri (N-N ara tablosu): her çıkarım için alan = değer
-- Kırtasiye fişinde vergi no 8 haneli -> gecerli_mi = false (doğrulamaya takıldı)
-- ---------------------------------------------------------------------
INSERT INTO cikarim_degerleri (cikarim_id, alan_id, deger, guven_skoru, gecerli_mi, duzeltildi_mi)
SELECT ck.id, sa.id, d.deger, d.guven, d.gecerli, d.duzeltildi
FROM cikarim_kayitlari ck
JOIN belgeler b ON b.id = ck.belge_id
JOIN (VALUES
    ('market_fisi_001.jpg', 'firma_adi',    'Ornek Market (Örnek)',     0.950, true,  false),
    ('market_fisi_001.jpg', 'vergi_no',     '1111111111',               0.990, true,  false),
    ('market_fisi_001.jpg', 'tarih',        '2026-10-12',               0.930, true,  false),
    ('market_fisi_001.jpg', 'kdv_tutari',   '22.50',                    0.880, true,  false),
    ('market_fisi_001.jpg', 'toplam_tutar', '247.50',                   0.920, true,  false),
    ('akaryakit_fisi.jpg',  'firma_adi',    'Ornek Akaryakit (Örnek)',  0.980, true,  false),
    ('akaryakit_fisi.jpg',  'vergi_no',     '2222222222',               0.990, true,  false),
    ('akaryakit_fisi.jpg',  'tarih',        '2026-10-13',               0.960, true,  false),
    ('akaryakit_fisi.jpg',  'kdv_tutari',   '133.33',                   0.950, true,  true),
    ('akaryakit_fisi.jpg',  'toplam_tutar', '800.00',                   0.990, true,  false),
    ('kirtasiye_fisi.png',  'firma_adi',    'Ornek Kirtasiye (Örnek)',  0.700, true,  false),
    ('kirtasiye_fisi.png',  'vergi_no',     '33333333',                 0.550, false, false),
    ('kirtasiye_fisi.png',  'tarih',        '2026-10-14',               0.810, true,  false),
    ('kirtasiye_fisi.png',  'kdv_tutari',   '15.00',                    0.600, true,  false),
    ('kirtasiye_fisi.png',  'toplam_tutar', '90.00',                    0.640, true,  false)
) AS d(dosya_adi, alan_adi, deger, guven, gecerli, duzeltildi) ON d.dosya_adi = b.dosya_adi
JOIN sema_alanlari sa ON sa.sema_id = ck.sema_id AND sa.alan_adi = d.alan_adi;
