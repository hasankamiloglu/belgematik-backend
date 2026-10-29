# Hafta 6 – Çekirdek Modül A: Fotoğraf Yükleme ve Ön İşleme

**Geliştirilen modül:** Fotoğraf Yükleme ve Ön İşleme

## Yapılan teknik çalışmalar

- [x] **Görsel yükleme:** `POST /api/belgeler` (multipart), listeleme, tekil görüntüleme, görsel indirme, silme
- [x] **Ön işleme:** EXIF yön düzeltme, gri ton, küçültme, otomatik kontrast, keskinleştirme (`app/services/preprocessing/goruntu.py`)
- [x] **Kalite ölçümü:** keskinlik (Laplace), parlaklık, ışık patlaması, kontrast → 0–100 puan + uyarılar
- [x] **Kayıt:** migration `004_belge_on_isleme.sql` (hash, işlenmiş yol, boyut, kalite, uyarılar, yeni durum)
- [x] **İş kuralları:** tür/içerik uyumu, 10 MB, tekrar yükleme yasağı, kredi, sahiplik (`app/services/belge_servisi.py`)
- [x] **React:** Belgelerim sayfası, sürükle-bırak yükleme, kalite rozetleri, orijinal/işlenmiş karşılaştırma
- [x] 20 yeni test (toplam 61)

## Teslim edilen çıktılar

| Çıktı | Konum |
|---|---|
| Çalışan yükleme ve ön işleme | Backend `app/api/belgeler.py`, `app/services/belge_servisi.py`, `app/services/preprocessing/` · Frontend `src/pages/BelgelerSayfasi.jsx` |
| İlgili kod | yukarıdaki dosyalar + `db/migrations/004_belge_on_isleme.sql` |
| Kısa açıklama | `docs/on-isleme.md` |
| Testler | `tests/test_on_isleme.py`, `tests/test_belgeler.py` |

## Gösterilecek ilerleme (demo sırası)

1. `bireysel@ornek.test` ile giriş → Belgelerim (kalan kredi 20)
2. Normal fiş yükle → Kalite 100, kredi 19
3. Karşılaştır → orijinal / ön işlenmiş yan yana
4. Bulanık fiş → uyarıyla kabul · Çok bulanık / küçük → red, kredi düşmez
5. Aynı dosyayı tekrar yükle → "zaten yüklediniz"
6. Başka kullanıcıyla giriş → ilk kullanıcının belgeleri görünmüyor
7. `pytest` → 61 test

## Kontrol kriterleri

| Kriter | Kanıt |
|---|---|
| Yükleme ve ön işleme çalışıyor | `test_yukleme_on_isler_ve_kredi_duser`, `test_on_isleme_gri_ve_kucultulmus`, `test_exif_yonu_duzeltilir` |
| Doğrulama / iş kuralları uygulanıyor | `test_sahte_uzanti_reddedilir`, `test_cok_bulanik_reddedilir`, `test_ayni_dosya_iki_kez_yuklenemez`, `test_kredi_bitince_yukleme_yapilamaz`, `test_10mb_ustu_dosya_reddedilir` |
| Önceki modüllerle tutarlı | Hafta 5 token ile sahiplik: `test_baskasinin_belgesi_gorulemez_silinemez` · Hafta 4 kredi CHECK'i · eski 41 test hâlâ geçiyor |

## Yapay zekâ kullanımı

Yapay zekâ; OCR öncesi görüntü iyileştirme yöntemlerini (gri ton, kontrast, keskinleştirme, eşikleme),
bulanıklık ölçme yaklaşımlarını (Laplace varyansı) ve `belgeler` tablosu için kolon/kısıt önerilerini
araştırmak, ayrıca servis kodunu katmanlara ayırma (refaktör) önerisi almak için kullanıldı.

## Öğrencinin kendi geliştirdiği bölümler

- Çekirdek mantık: kalite ölçümü ve ön işleme akışı (`goruntu.py`); eşikler örnek görsellerle ölçülerek belirlendi
- İş kuralları ve doğrulama: tekrar yükleme yasağı, kredi + kayıt transaction'ı, sahiplik (`belge_servisi.py`)

## Sık yapılan hatalara karşı

| Hata | Bu projede |
|---|---|
| Doğrulamayı atlamak | Uzantı + içerik + boyut + kalite sunucuda kontrol ediliyor |
| Erişim/sahiplik kontrolünü unutmak | Her sorguda `WHERE id = ? AND kullanici_id = ?`; başkasının belgesi 404 |
| İlişkili kayıtları yönetmemek | Kayıt + kredi tek transaction; DB hatasında diske yazılan dosyalar geri siliniyor; belge silinince dosyalar da siliniyor |
