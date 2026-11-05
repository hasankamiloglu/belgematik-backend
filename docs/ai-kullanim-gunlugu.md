# Yapay Zekâ Kullanım Günlüğü

**Öğrenci:** Hasan Kamiloğlu · **Proje:** P57 Görüntüden Yapılandırılmış Veri Çıkarma (Belgematik)
**Kullanılan araç:** Claude (Anthropic), sohbet tabanlı yapay zekâ asistanı
**Güncelleme:** Hafta 8 – Ara sürüm v0.7.0

## Nasıl kullanıldı? (genel)

Yapay zekâ projede **eşli programlama (pair programming) ortağı** olarak kullanıldı:

| Yapay zekânın yaptığı | Öğrencinin yaptığı |
|---|---|
| Haftalık gereksinimlere göre mimari, kod, test ve doküman taslaklarını yazdı | Her haftanın gereksinimlerini verdi, yönü belirledi (ör. React seçimi, ayrı depolar) |
| Kodun her satırına Türkçe açıklama ekledi | Geliştirme ortamını kendisi kurdu: Python, VS Code, Git/GitHub, PostgreSQL, Node.js, Tesseract |
| Kavramları adım adım anlattı | Tüm komutları kendi bilgisayarında çalıştırdı, testleri koşturdu, ekranları denedi |
| Öğrencinin bildirdiği hataları analiz edip düzeltti | Hataları bulup bildirdi (aşağıdaki tabloda), düzeltmeleri doğruladı |
| | Kodu GitHub'a yükledi, demo yaptı, sözlü sorulara hazırlandı |

> **Not:** Kodun büyük bölümü yapay zekâ tarafından üretildi. Bu nedenle öğrencinin asıl sorumluluğu
> kodu **çalıştırmak, doğrulamak ve açıklayabilmek** oldu. Açıklanamayan kod taşımamak için her
> hafta sözlü sorular üzerinden kod satır satır çalışıldı.

## Haftalık kayıt

| Hafta | Yapay zekâdan istenen | Alınan çıktı | Öğrencinin doğrulaması / katkısı | Öğrenilen |
|---|---|---|---|---|
| 3 | Proje fikri, teknoloji seçimi, iskelet, ER diyagramı | Flask iskeleti, 3 katmanlı klasör yapısı, diyagramlar, README | Python/VS Code/Git kurulumu, GitHub hesabı, ilk commit; hocanın isteğiyle frontend/backend'i ayırma kararı | Katmanlı mimari, `.env`, `.gitignore`, sanal ortam |
| 4 | PostgreSQL şeması, kısıtlar, indeksler, CRUD | 7 tablo, migration aracı, repository'ler, 15 test | PostgreSQL kurulumu: Türkçe yerel ayar hatası alındı, "C" yerel ayarıyla yeniden kuruldu; migrate/seed/test çalıştırıldı, pgAdmin'de kontrol | PK/FK, CASCADE/RESTRICT, UNIQUE, CHECK, indeks, parametreli sorgu (SQL injection) |
| 5 | Kayıt/giriş, parola hash, JWT, rol | PBKDF2 + tuz, JWT, `@yetki_gerekli`, kilitleme, React sayfaları | Gizli anahtar üretimi, testler (41), tarayıcıda 401/403 denemeleri | Hash ve tuz, oturum vs token, 401 vs 403 |
| 6 | Fotoğraf yükleme ve ön işleme | Pillow ile kalite ölçümü ve ön işleme, iş kuralları | **Windows'ta testin düştüğünü buldu** (açık dosya silinemiyor) → düzeltildi; örnek fişlerle deneme | EXIF, gri ton, kontrast, SHA-256, transaction |
| 7 | OCR, alan eşleme, doğrulama | Tesseract entegrasyonu, eşleyici, VKN/KDV kuralları, şema ekranı | Tesseract'ı Türkçe dil paketiyle kurdu; **3 testin düştüğünü buldu** → iki gerçek hata düzeltildi (RESTRICT hata kodu, Türkçe modelin "%" işaretini "4" okuması) | OCR güveni, anahtar kelime eşleme, kontrol hanesi algoritması, iş kuralı |
| 8 | Entegrasyon, hata giderme, ara sürüm | Uçtan uca test, GitHub Actions, CHANGELOG, bu günlük, ilerleme raporu | Ara sürümü etiketledi (`git tag v0.7.0`), Actions sonuçlarını kontrol etti, demo senaryosunu prova etti | Anlamsal sürümleme, entegrasyon ve regresyon testi |

## Yapay zekâ çıktısının doğrulanması

Yapay zekânın yazdığı kod **olduğu gibi kabul edilmedi**. Her hafta:
1. Otomatik testler öğrencinin bilgisayarında çalıştırıldı (Hafta 8: 99 test).
2. Ekranlar tarayıcıda elle denendi (doğru/hatalı örnek belgelerle).
3. Öğrencinin bilgisayarında çıkan hatalar yapay zekâya geri bildirildi ve düzeltildi.
   Yapay zekânın kendi ortamında (Linux) görünmeyen 4 hata bu sayede bulundu.

## Yapay zekânın hataları (dürüst kayıt)

| Hafta | Hata | Nasıl fark edildi |
|---|---|---|
| 3 | HTML yorumu içindeki şablon etiketi sayfayı bozdu | Sayfa açılmadı |
| 6 | Windows'ta açık dosya silinemediği için test düştü | Öğrencinin `pytest` çıktısı |
| 7 | PostgreSQL'in RESTRICT hata kodu yanlış yakalandı | Öğrencinin `pytest` çıktısı |
| 7 | Türkçe OCR modeliyle "%20" → "420" okuma hatası öngörülmedi | Öğrencinin `pytest` çıktısı |
