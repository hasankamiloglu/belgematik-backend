# Alan Eşleme ve Doğrulama Modülü (Hafta 7)

## 1. Akış

```
Belgelerim → "Verileri çıkar" → şema seç
        │
        ▼  POST /api/belgeler/<id>/isle  {"sema_id": 1}
cikarim_servisi.belge_isle()
  1) Sahiplik: belge bu kullanıcının mı? (değilse 404)
  2) Şema: sistem şeması veya kullanıcının kendi şeması mı? (değilse 404)
  3) OCR        ocr/tesseract.py          ön işlenmiş görsel → ham metin + okuma güveni
  4) EŞLEME     extraction/eslestirici.py  ham metin + şema alanları → {alan: değer, güven, yöntem}
  5) DOĞRULAMA  validation/dogrulayici.py  alan kuralları + iş kuralları
  6) KAYIT      cikarim_repo.sonuc_kaydet  cikarim_kayitlari + cikarim_degerleri + belge 'islendi'
                                           (tek transaction)
```

## 2. Şema tanımı

Şema, bir belge türünün kalıbıdır. Her alanda şunlar bulunur:

| Özellik | Örnek | Ne işe yarar |
|---|---|---|
| `alan_adi` | `toplam_tutar` | Alanın adı |
| `veri_tipi` | `metin` / `para` / `tarih` / `sayi` | Değerin nasıl okunacağı ve doğrulanacağı |
| `zorunlu_mu` | `true` | Bulunamazsa hata |
| `anahtar_kelimeler` | `GENEL TOPLAM,TOPLAM,-ARA,-KDV` | Eşleyici bu kelimeleri arar. `-` ile başlayan kelime o satırı eler |
| `dogrulama_kurali` | `^[0-9]{10,11}$` | Değerin uyması gereken düzenli ifade (regex) |

- **Sistem şemaları** (`fis`, `fatura`, `kartvizit`) herkese açıktır ve silinemez.
- **Kullanıcı şemaları** sadece sahibine görünür. Ekrandan tanımlanır (`#/semalar`). Bir çıkarımda kullanılmış şema silinemez (`ON DELETE RESTRICT` → 409).

## 3. Alan eşleme yöntemleri

| Sıra | Yöntem | Nasıl | Güven |
|---|---|---|---|
| 1 | Anahtar kelime | Kelimenin geçtiği satırdan, tipine göre değer okunur (satırlar **aşağıdan yukarı** taranır, toplamlar fişin altındadır) | 0,90 |
| 1b | Alt satır | Değer kelimenin altındaki satırdaysa | 0,80 |
| 2 | Kalıp | Kelime yoksa metnin her yerinde aranır: 10–11 haneli vergi no, gg.aa.yyyy, e-posta, telefon | 0,60 |
| 3 | Konum | Firma adı = fişin en üstteki anlamlı satırı | 0,60 |

**Alan güveni = yöntem güveni × OCR okuma güveni.** Örneğin %90 × %91 ≈ %82.

**OCR dili:** `eng+tur`. İngilizce önce, çünkü Türkçe model denemelerde `%20` yazısını `420` okudu (4 yazı tipi × 5 belgede `tur+eng` 4 hata, `eng+tur` 0 hata). Eşleyici yine de `420` → `%20` hatasını tolere eder.

Metin sadeleştirilir (`Fiş` → `FIS`, büyük harf). Para Türk biçiminde okunur (`1.234,56`). OCR'ın virgül yanına koyduğu boşluk (`800, 00`) tolere edilir. Farklı KDV oranlı ürünler varsa tek bir oran yoktur, bu yüzden `kdv_orani` boş bırakılır.

## 4. Doğrulama

**Alan kuralları** (`alan_dogrula`):
1. Zorunlu alan boş mu?
2. Veri tipi: tarih gerçek mi, gelecekte değil mi, 2000 öncesi değil mi? Para pozitif mi? Sayı mı?
3. Şemadaki regex kuralı
4. Alana özel kurallar:
   - **Vergi no kontrol hanesi**: VKN için GİB algoritması, 11 hane için TCKN algoritması
   - E-posta ve telefon biçimi
   - KDV oranı Türkiye'de kullanılan oranlardan biri mi (0, 1, 8, 10, 18, 20)

**İş kuralları** (`is_kurallari`), alanlar birbiriyle tutarlı mı:

| Kural | Ne zaman | Tolerans |
|---|---|---|
| KDV < Toplam | KDV ve toplam bulunduysa | – |
| KDV = Toplam × oran / (100 + oran) | Fişte tek KDV oranı varsa | 0,05 TL |
| Matrah + KDV = Toplam | Faturada matrah varsa | 0,05 TL |

Tüm alanlar ve kurallar geçerliyse çıkarım durumu `dogrulandi`, değilse `bekliyor` olur (kullanıcı kontrol etmeli).

## 5. Veri modeli (migration `005_alan_esleme_dogrulama.sql`)

| Tablo | Eklenen | Neden |
|---|---|---|
| `sema_alanlari` | `anahtar_kelimeler`, `sira` | Eşleme ipuçları ve ekrandaki sıra |
| `cikarim_degerleri` | `hata_mesaji` | Alan neden geçersiz |
| `cikarim_kayitlari` | `kural_sonuclari` (JSONB), `kullanici_id` | İş kuralı sonuçları ve sahiplik |

`cikarim_degerleri`, çıkarım ile şema alanı arasındaki **N-N ara tablodur** (Hafta 4).

## 6. Entegrasyon

| Modül | Bağlantı |
|---|---|
| Hafta 4 – Veritabanı | `semalar`, `sema_alanlari`, `cikarim_kayitlari`, `cikarim_degerleri` tabloları kullanıldı ve genişletildi |
| Hafta 5 – Kimlik | Tüm uçlar `@giris_gerekli`; kullanıcı token'dan alınır |
| Hafta 6 – Ön işleme | OCR, ön işlenmiş görseli (`islenmis_yol`) okur; sahiplik için `belge_servisi.getir` kullanılır |
| Frontend | Belgelerim → "Verileri çıkar" penceresi, Şemalar sayfası |

## 7. Bilinen sınırlar

- PDF'ler henüz OCR'a girmiyor (sayfayı görsele çevirme eklenecek).
- Eşleme kurala dayalı. Karmaşık fatura düzenlerinde "pro" pakette yapay zekâ motoru kullanılacak.
- Yanlış bulunan değerleri ekrandan düzeltme sonraki modüldür (`cikarim_repo.deger_duzelt` hazır).
