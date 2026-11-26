"""
ai paketi - Yapay zekâ ile yapılandırılmış veri çıkarımı (Hafta 10).

    istem.py               -> Modele gönderilen istemi (prompt) ve JSON şemasını hazırlar
    gemini.py              -> Google Gemini API istemcisi (görsel + istem -> JSON metni)
    cikti_dogrulama.py     -> Modelin çıktısını DOĞRULAR: JSON mu, şemaya uyuyor mu,
                              değer biçimleri doğru mu, OCR metninde gerçekten var mı?
    yapay_zeka_cikarici.py -> Hepsini sırayla çalıştırır ve API çağrısını günlüğe yazar

Akış:  görsel ─▶ istem + şema ─▶ Gemini ─▶ JSON ─▶ DOĞRULAMA ─▶ {alan: değer, güven}
                                                   (hatalıysa kural tabanlı eşleyiciye dönülür)

Yapay zekânın çıktısına KÖRÜ KÖRÜNE GÜVENİLMEZ: her alan, kural tabanlı sistemin
kullandığı aynı doğrulama kurallarından da geçer (VKN kontrol hanesi, KDV hesabı...).
"""
