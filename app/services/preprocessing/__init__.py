"""
preprocessing paketi - Görsel ön işleme (Hafta 6).

    goruntu.py -> Dosyanın gerçekten görsel olup olmadığını kontrol eder,
                  kalitesini ölçer ve OCR için düzeltir.

Neden ön işleme? OCR (Hafta 7) temiz, düz, kontrastı yüksek görselde çok daha
doğru okur. Telefonla çekilmiş fiş genelde yan dönmüş, gölgeli, renkli ve
gereğinden büyüktür. Ön işleme bunları OCR'dan ÖNCE düzeltir.

Bu modül Flask'ı ve veritabanını BİLMEZ: sadece bayt alır, sonuç döndürür.
Böylece tek başına test edilebilir.
"""
