# Fotoğraf Yükleme ve Ön İşleme Modülü (Hafta 6)

## 1. Akış

```
Tarayıcı (React)                 Backend (Flask)
-----------------                ------------------------------------------------------------
Dosya seç / sürükle  ──POST──▶  api/belgeler.py      @giris_gerekli, dosyayı al
(tür + boyut ön kontrol)         services/belge_servisi.py
                                   1) uzantı, boş dosya, 10 MB
                                   2) SHA-256 → aynı dosya daha önce yüklendi mi?  (409)
                                   3) kredi var mı?                               (402)
                                   4) preprocessing/goruntu.py
                                        - gerçekten görsel mi, uzantı içerikle aynı mı?
                                        - EXIF yön düzeltme
                                        - çözünürlük kontrolü (kısa kenar ≥ 400 px)
                                        - kalite ölçümü → puan + uyarılar
                                        - gri ton → küçült (≤ 2000 px) → kontrast → keskinleştir
                                   5) diske yaz: uploads/<kullanici_id>/<uuid>.jpg (+ _islenmis.png, _kucuk.jpg)
                                   6) TEK TRANSACTION: belgeler INSERT + kredi −1
Sonuç + uyarılar     ◀──201───
```

## 2. Ön işleme adımları ve nedenleri

| Adım | Pillow | Neden |
|---|---|---|
| Yön düzeltme | `ImageOps.exif_transpose` | Telefon "yan çektim" bilgisini EXIF'e yazar; düzeltilmezse OCR yan yazıyı okuyamaz |
| Gri tonlama | `ImageOps.grayscale` | Renk metin okumaya katkı vermez; veri 3 kat azalır |
| Küçültme | `thumbnail((2000, 2000), LANCZOS)` | 12 MP fotoğraf gereksiz büyük; OCR için 2000 px yeterli ve hızlı |
| Otomatik kontrast | `ImageOps.autocontrast(cutoff=1)` | Gölgeli/soluk fişte yazıyı siyaha, kâğıdı beyaza çeker |
| Keskinleştirme | `UnsharpMask(2, 120, 3)` | Harf kenarlarını netleştirir |

Orijinal dosya **değiştirilmeden** saklanır; ön işlenmiş sürüm ayrı dosyadır (düzeltme ekranında ikisi karşılaştırılabilir).

## 3. Düşük kaliteli görsel

| Ölçüm | Nasıl | Eşik | Sonuç |
|---|---|---|---|
| Bozuk / sahte dosya | `Image.verify()`, biçim ≠ uzantı | – | **Red** (400) |
| Çözünürlük | kısa kenar | < 400 px | **Red** |
| Aşırı piksel | `MAX_IMAGE_PIXELS` | > 40 M | **Red** (sıkıştırma bombası) |
| Keskinlik | Laplace filtresi varyansı | < 20 / < 100 | Red / uyarı (−35) |
| Karanlık | ortalama parlaklık | < 60 | uyarı (−30) |
| Işık patlaması | tam beyaz piksel oranı | > %40 | uyarı (−30) |
| Kontrast | koyu (%0,2) – açık (%99) ton farkı | < 100 | uyarı (−20), otomatik düzeltilir |

Puan 100'den başlar; **40'ın altı reddedilir**, arası **uyarıyla** kaydedilir. Reddedilen görselde **kredi düşmez**.
Eşikler sentetik fiş görselleriyle (`tests/ornek_gorsel.py`) ölçülerek belirlendi.

## 4. Veri modeli (migration `004_belge_on_isleme.sql`)

`belgeler` tablosuna eklenen kolonlar:

| Kolon | Tip | Açıklama |
|---|---|---|
| `dosya_hash` | CHAR(64) | SHA-256; `UNIQUE (kullanici_id, dosya_hash)` |
| `islenmis_yol`, `kucuk_yol` | VARCHAR(500) | ön işlenmiş görsel ve önizleme (PDF'te NULL) |
| `genislik`, `yukseklik` | INTEGER, CHECK > 0 | orijinal boyut |
| `kalite_puani` | SMALLINT, CHECK 0–100 | kalite puanı |
| `kalite_uyarilari` | JSONB | uyarı listesi |

Durum akışı: `yuklendi` (PDF) / `on_islendi` (görsel, OCR'a hazır) → `islendi` → `hatali`

## 5. İş kuralları

1. Sadece PNG / JPG / JPEG / PDF; **uzantı içerikle uyuşmalı** (`fis.jpg` adlı bir PNG veya .exe reddedilir).
2. En fazla 10 MB (Flask `MAX_CONTENT_LENGTH` → 413).
3. **Aynı kullanıcı aynı dosyayı iki kez yükleyemez** (409). Çift kayıt ve çift kredi harcamayı önler.
4. **Her yükleme 1 kredi**; kredi bitince 402. Kayıt ve kredi düşme **tek transaction**.
5. **Sahiplik:** kullanıcı id'si istekten değil **token'dan** alınır. Başkasının belgesi istenirse 404 döner (varlığı bile söylenmez). Yönetici de başkalarının fişlerini göremez (KVKK: gereksiz erişim yok).
6. Disk adı **rastgele** (`uuid4`), kullanıcının dosya adı diske yazılmaz (yol saldırısı `../../` engellenir).
7. Silinen belgenin dosyaları da diskten silinir; harcanan kredi iade edilmez.

## 6. Diğer modüllerle entegrasyon

| Modül | Bağlantı |
|---|---|
| Hafta 4 – Veritabanı | `belgeler` tablosu genişletildi (migration 004), `belge_repo` yeni fonksiyonlar |
| Hafta 4 – Abonelik | `kullanici_repo.kredi_dus` ile kredi düşer, CHECK kısıtı eksiye düşmeyi engeller |
| Hafta 5 – Kimlik | Tüm uçlar `@giris_gerekli`; sahip `g.kullanici["id"]` |
| Hafta 7 – OCR | `islenmis_yol` + `durum = 'on_islendi'` → OCR bu belgeleri işleyecek |
| Frontend | `#/belgeler` sayfası; görseller token'la indirilir (`gorselAdresi`) |

## 7. Bilinen sınırlar

- PDF'ten görsel üretme OCR haftasında eklenecek (şimdilik PDF sadece saklanıyor).
- Eğik çekilmiş fişi düzleştirme (perspektif düzeltme) ve ikili renge çevirme (eşikleme) OCR sonuçlarına göre değerlendirilecek.
- Dosyalar sunucu diskinde; canlıya geçerken bulut depolama (S3 vb.) düşünülecek.
