# Harici OCR API Entegrasyonu (Hafta 9)

Belgematik artık OCR için iki motor kullanabiliyor:

| Motor | Nerede çalışır | Artısı | Eksisi |
|---|---|---|---|
| **Tesseract** (Hafta 7) | Bilgisayarda | Ücretsiz, internet gerekmez | Kurulum ister, bazı fişlerde zorlanır |
| **OCR.space** (Hafta 9) | Bulutta (REST API) | Kurulum yok, temiz okuma | Anahtar ister, günde 500 istek, 1 MB dosya sınırı |

## 1. Akış

```
React "Verileri çıkar"
   │  POST /api/belgeler/<id>/isle
   ▼
cikarim_servisi.belge_isle
   │
   ▼
motor_secici.metin_oku  ── OCR_MOTORU = ?
   │
   ├─ tesseract ───────────────▶ Tesseract
   │
   └─ otomatik / api
        │ 1) kendi hız sınırımız dolu mu?     (dakikada 10)
        │ 2) görseli JPEG'e çevir, 1 MB altına indir
        │ 3) POST https://api.ocr.space/parse/image
        │       başlık: apikey (.env'den)    zaman aşımı: 5 sn bağlanma, 30 sn cevap
        │ 4) cevabı ayrıştır (ParsedResults -> metin)
        │
        ├─ başarılı ──────────────▶ metin  (api_cagrilari: basarili)
        └─ hata
             ├─ geçici (zaman aşımı, bağlantı, 5xx) -> 1 sn / 2 sn bekle, en fazla 3 deneme
             ├─ otomatik modda -> Tesseract YEDEK  (api_cagrilari: hata, sonuç notu)
             └─ api modunda    -> kullanıcıya 503 hatası
   │
   ▼
alan eşleme -> doğrulama -> kayıt (Hafta 7, değişmedi)
```

## 2. Kurulum (5 dakika)

1. **Ücretsiz anahtar alın:** <https://ocr.space/ocrapi/freekey>. E-postanızı yazın, anahtar e-postanıza gelir.
2. Backend klasöründeki **`.env`** dosyasına ekleyin (`.env.example` dosyasına değil!):
   ```
   OCR_MOTORU=otomatik
   OCR_API_ANAHTARI=buraya-e-postayla-gelen-anahtar
   ```
3. Kontrol edin:
   ```
   python manage.py migrate
   python manage.py ocr-api-kontrol
   ```
   Çıktıda `✔ API çalışıyor` ve okunan metin görünmeli.

## 3. Ayarlar (`.env`)

| Değişken | Varsayılan | Anlamı |
|---|---|---|
| `OCR_MOTORU` | `otomatik` | `otomatik` (API → hata olursa Tesseract), `api`, `tesseract` |
| `OCR_API_ANAHTARI` | boş | OCR.space anahtarı. **Sadece `.env`'de** |
| `OCR_API_DIL` | `tur` | Dil kodu |
| `OCR_API_MOTOR` | `1` | OCR.space'in 1 numaralı motoru Türkçeyi destekliyor |
| `OCR_API_DAKIKA_SINIRI` | `10` | Kendi hız sınırımız (dakikadaki çağrı sayısı) |

## 4. API anahtarının güvenliği

| Kural | Nasıl sağlanıyor |
|---|---|
| Anahtar kodda değil | `harici_api.py` anahtarı `os.getenv("OCR_API_ANAHTARI")` ile okur |
| Anahtar depoda değil | `.env` → `.gitignore`. Test: `test_depoda_env_dosyasi_takip_edilmiyor` |
| Örnek dosyada değil | `.env.example` içinde `OCR_API_ANAHTARI=` boş. Test: `test_env_example_da_gercek_anahtar_yok` |
| Loglarda / veritabanında değil | `api_cagrilari` tablosunda anahtar kolonu yok |
| Ekranda değil | Yönetici paneli sadece maskeli hali gösterir: `K8****1234` |
| Tarayıcıya gitmiyor | API'yi backend çağırır; React anahtarı hiç görmez |

> Anahtar yanlışlıkla GitHub'a gönderilirse: OCR.space'ten **yeni anahtar alın**, eskisini kullanmayın.
> Commit'i silmek yetmez, çünkü Git geçmişi kopyalanmış olabilir.

## 5. Hata yönetimi

| Durum | Tür | HTTP | Ne yapılıyor? |
|---|---|---|---|
| `.env`'de anahtar yok | `anahtar_yok` | – | API'ye gidilmez; otomatik modda Tesseract |
| Anahtar yanlış | `kimlik` | 401 / 403 | Tekrar denenmez (boşuna) |
| Çok fazla istek | `hiz_siniri` | 429 | Tekrar denenmez; yedek motor |
| Kendi sınırımız doldu | `hiz_siniri` | – | API'ye hiç gidilmez |
| Cevap gelmedi | `zaman_asimi` | – | 1 sn, sonra 2 sn bekleyip tekrar (en fazla 3 deneme) |
| İnternet yok | `baglanti` | – | Tekrar denenir |
| Servis çöktü | `sunucu` | 5xx | Tekrar denenir |
| Cevap bozuk / boş | `yanit` | 200 | Tekrar denenmez |
| Görsel çok büyük | `dosya` | – | Önce sıkıştırılır; olmazsa hata |

**Neden bazıları tekrar denenir?** Zaman aşımı ve sunucu hatası **geçicidir**; birkaç saniye sonra düzelebilir.
Yanlış anahtar ise **kalıcıdır**; tekrar denemek sadece kotayı harcar.

**Üstel geri çekilme (exponential backoff):** Her denemede bekleme süresi ikiye katlanır (1 sn → 2 sn).
Böylece zaten zorlanan servise art arda istek yağdırmayız.

**OCR.space'in özelliği:** Bazı hatalarda HTTP 200 döndürür; hata bilgisi gövdededir
(`"IsErroredOnProcessing": true`). Bu yüzden sadece HTTP koduna değil, gövdeye de bakıyoruz.

## 6. Yanıt ayrıştırma

OCR.space cevabı:
```json
{
  "ParsedResults": [ { "ParsedText": "ORNEK MARKET A.S.\r\nTOPLAM 120,00\r\n" } ],
  "OCRExitCode": 1,
  "IsErroredOnProcessing": false,
  "ErrorMessage": null
}
```
`yaniti_cozumle()` fonksiyonu sırasıyla şunları yapar:
1. Cevap JSON değilse hata verir.
2. `IsErroredOnProcessing` doğruysa `ErrorMessage` içindeki mesajı okuyup hata türünü bulur.
3. `ParsedResults` boşsa hata verir.
4. Her sayfanın `ParsedText` metnini birleştirir, `\r\n` → `\n` çevirir.

**`isTable=true` neden gönderiliyor?** İlk denemede bu ayar yoktu. Servis fişin sol sütununu
(`TOPKDV`, `TOPLAM`) ve sağ sütununu (`41,25`, `247,50`) ayrı bloklar halinde döndürdü ve eşleyici
KDV tutarını ve toplamı bulamadı. `isTable=true` metni satır satır döndürüyor. Fiş ve fatura
için servisin önerdiği ayar da budur.

Sonuç Tesseract ile **aynı biçimde** döner (`{"metin", "guven", "motor"}`), bu yüzden alan eşleme ve doğrulama kodu hiç değişmedi.
OCR.space kelime güveni vermediği için güven sabit **0.90** alınır.

## 7. Testler (internete çıkmadan)

`tests/test_harici_api.py` dosyası `requests.post` yerine **sahte** bir fonksiyon koyar (monkeypatch) ve her durumu taklit eder:
başarılı cevap, 401/403, 429, zaman aşımı (2 kez sonra başarı / hep), bağlantı hatası, 503, JSON olmayan cevap, boş sonuç, büyük görsel, yedek motor.
Gerçek kota harcanmaz ve testler internetsiz de çalışır.

`tests/conftest.py`, testlerde `OCR_MOTORU=tesseract` yapar. Böylece `.env`'de anahtar olsa bile normal testler gerçek API'yi çağırmaz.

## 8. Yönetici paneli

`GET /api/yonetici/api-cagrilari` (sadece yönetici) şunları döndürür:
- seçili motor, maskeli anahtar, dakika sınırı,
- son 24 saatin özeti (toplam / başarılı / hatalı / ortalama süre),
- son 30 çağrı (tarih, kullanıcı, durum, hata türü, HTTP kodu, deneme, süre).
