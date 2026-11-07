# LeadGen Engine 🔎

İşletme iletişim verisi toplama suite'ı — **2 bağımsız motor**:

| Motor | Dosya | Kaynak | Ne zaman |
|---|---|---|---|
| **OSM/Overpass** | `leadgen_osm.py` | OpenStreetMap | Yapısal veri, yüksek hacim, ücretsiz (tercihen ilk seçenek) |
| **Dizin scraping** | `scrape_directory.py` | Dizin siteleri (crawl4ai) | JS ağırlıklı/api kapalı siteler için |

## Çıktı ne içerir?
İşletme adı, kategori, telefon, website, e-posta (varsa), adres, çalışma saatleri + **iletişim skoru** (1-3).

## Hızlı kullanım
```bash
pip install -r requirements.txt   # requests
python leadgen_osm.py --city "Kadıköy" --types cafe,restaurant,bar --out leads.csv
python leadgen_osm.py --bbox 40.98,28.97,41.02,29.03 --types fitness,clinic --out leads.csv
python scrape_directory.py --config config.json
```
Nginx/Overpass rate-limit hatası alınırsa script otomatik 3 farklı endpoint + exponensial backoff ile tekrar dener.

## Kullanım alanları (ticari)
- B2B satış lead listesi üretimi
- E-posta/WhatsApp pazarlama kampanyaları
- Rakip şube/konum haritalama
- Franchise/pazaranalizi

## Demo (gerçek veri)
`demo/` klasöründe İstanbul Kadıköy örnek çıktıları.

## ⚠️ Etik/KVKK notu
Toplanan verilerin kullanımı firmaların açık iletişim bilgileriyle sınırlıdır; GDPR/KVKK uyumlu pazarlama ve "abonelikten çıkma" linki zorunludur.
