# Hafta 9 – Harici API Entegrasyonu: Vision / OCR

**Geliştirilen modül:** Vision/OCR entegrasyonu (OCR.space REST API) · Sürüm `v0.8.0`

## Yapılan teknik çalışmalar

- [x] **Vision/OCR API:** `app/services/ocr/harici_api.py`. Görsel `POST https://api.ocr.space/parse/image` adresine gönderiliyor, metin JSON olarak alınıyor
- [x] **Çıkarım akışı:** `motor_secici.py` → önce API, hata olursa Tesseract (yedek) → alan eşleme → doğrulama → kayıt
- [x] **Hata yönetimi:** 8 hata türü, zaman aşımı (5 sn / 30 sn), 3 deneme + üstel geri çekilme, kendi hız sınırımız (dakikada 10)
- [x] **API anahtarı ortam değişkeninde:** `.env` → `OCR_API_ANAHTARI`; depoda, logda ve veritabanında yok
- [x] **Çağrı günlüğü:** `api_cagrilari` tablosu (migration 006) + yönetici paneli
- [x] `python manage.py ocr-api-kontrol` · Toplam **127 test** (28 yeni)

## Teslim edilen çıktılar

| Çıktı | Konum |
|---|---|
| Çalışan API entegrasyonu | `app/services/ocr/harici_api.py`, `motor_secici.py` · Belgelerim → "Verileri çıkar" |
| Hata yönetimi | `harici_api.py` (ApiHatasi, tekrar deneme, hız sınırı) · `docs/harici-api.md` bölüm 5 |
| Testler | `tests/test_harici_api.py`, `tests/test_api_entegrasyonu.py` |

## Kontrol kriterleri

| Kriter | Kanıt |
|---|---|
| API anahtarı depoda değil | `.gitignore` → `.env`; GitHub'da arama: anahtar yok; 3 güvenlik testi |
| Hatalar yönetiliyor | Yanlış anahtar → Tesseract ile devam + not; `api` modunda 503; günlükte hata türü |
| Entegrasyon doğru | `ocr-api-kontrol` çıktısı; fiş API ile okunup doğrulanıyor (`ocr_motoru = ocr_space`) |

## Kavramlar

| Kavram | Bu projede |
|---|---|
| **REST** | HTTP üzerinden kaynakla konuşma: `POST /parse/image` + form verisi → JSON cevap |
| **API kimlik doğrulama** | `apikey` başlığı. Yanlışsa 401/403. Anahtar `.env`'den okunur |
| **Rate limit (hız sınırı)** | Servis: günde 500, aşınca 429. Biz: dakikada 10 (kayan pencere) |
| **Zaman aşımı** | `timeout=(5, 30)`. Cevap gelmezse sonsuza kadar beklenmez |
| **Hata yönetimi** | Geçici hatalar tekrar denenir, kalıcılar denenmez; otomatik modda yedek motor |

## Sık yapılan hatalara karşı

| Hata | Bu projede |
|---|---|
| Anahtarı koda gömmek | `os.getenv("OCR_API_ANAHTARI")`; test `.env.example`'da anahtar olmadığını kontrol ediyor |
| Hataları yakalamamak | Her hata `ApiHatasi(tur=...)`; servis katmanı 503'e çeviriyor |
| Zaman aşımı yönetmemek | Her istekte `timeout`; zaman aşımında 3 deneme |

## Sözlü sınav soruları

1. **OCR'ı nasıl entegre ettin?** Görseli backend'den OCR.space'e REST ile gönderiyorum (`POST /parse/image`), metni JSON olarak alıyorum. Motor seçici önce API'yi deniyor, olmazsa Tesseract'ı kullanıyor. Sonraki adımlar (eşleme, doğrulama) değişmedi.
2. **API başarısızsa ne yapıyorsun?** Geçici hatada 1 sn, sonra 2 sn bekleyip 3 kez deniyorum. Yine olmazsa Tesseract ile okuyorum ve kullanıcıya not gösteriyorum. Her hata günlüğe yazılıyor.
3. **API anahtarını nasıl ve nerede sakladın?** `.env` dosyasında. Bu dosya `.gitignore`'da olduğu için GitHub'a gitmiyor. Kod anahtarı ortam değişkeninden okuyor; ekranda sadece maskeli hali görünüyor.
4. **API çağrısı başarısızsa ne oluyor?** Hatanın türüne bakıyorum: yanlış anahtar veya hız sınırı ise tekrar denemiyorum, zaman aşımı veya sunucu hatası ise tekrar deniyorum. Sonunda yedek motor devreye giriyor; `api` modundaysa kullanıcı 503 hatası görüyor.
5. **Yanıtı nasıl ayrıştırıyorsun?** JSON'da önce `IsErroredOnProcessing` alanına bakıyorum; doğruysa hata mesajını okuyorum. Değilse `ParsedResults` içindeki `ParsedText` metinlerini birleştirip satır sonlarını düzeltiyorum.
