"""
Repository (depo) deseni: Her tablo grubu için veri erişim (CRUD) fonksiyonları.

    kullanici_repo.py -> kullanicilar + abonelikler
    belge_repo.py     -> belgeler
    cikarim_repo.py   -> cikarim_kayitlari + cikarim_degerleri (N-N ara tablo)
    kimlik_repo.py    -> giriş/çıkış ile ilgili kolonlar + giris_denemeleri (Hafta 5)

CRUD = Create (ekle) / Read (oku) / Update (güncelle) / Delete (sil)

Kurallar:
  - SQL SADECE bu klasörde yazılır. İş katmanı (services) SQL bilmez,
    sadece bu fonksiyonları çağırır.
  - Her fonksiyon ilk parametre olarak bağlantıyı (conn) alır. Böylece
    birden fazla fonksiyon AYNI transaction içinde çalıştırılabilir.
  - Değerler SQL'e asla string birleştirerek eklenmez; %s yer tutucusu
    kullanılır. Bu, SQL INJECTION saldırısını önler.
"""
