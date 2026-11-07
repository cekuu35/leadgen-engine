#!/usr/bin/env python3
"""
OSM LeadGen — OpenStreetMap Overpass API ile gerçek işletme verisi.
Mahalle/ilçe + sektör seç, telefon+web+adresli temiz lead listesi al.

Kullanım:
  python leadgen_osm.py --city "Kadıköy" --types cafe,restaurant,bar --out leads.csv
  python leadgen_osm.py --bbox 28.97,41.00,29.03,41.03 --types fitness --out gyms.csv
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import requests

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]

TEL_KEYS = ["phone", "contact:phone", "telephone", "contact:telephone"]
WEB_KEYS = ["website", "contact:website", "url"]
EMAIL_KEYS = ["email", "contact:email"]
ADDR_KEYS = ["addr:street", "addr:housenumber", "addr:city", "addr:postcode"]


def build_query(city: str | None, bbox: str | None, types: list[str]) -> str:
    sel = "|".join(types)
    if bbox:
        south, west, north, east = bbox.split(",")
        area_stmt = ""
        where = f"({south},{west},{north},{east})"
    else:
        area_stmt = f'area["name"="{city}"]["admin_level"~"^(7|8)$"]->.a;'
        where = "(area.a)"
    return f"""[out:json][timeout:90];
{area_stmt}(
  node["amenity"~"{sel}"]["name"]{where};
  way["amenity"~"{sel}"]["name"]{where};
);
out center tags;"""


def query_overpass(q: str, retries: int = 4) -> list[dict]:
    last_err = None
    for attempt in range(retries):
        ep = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            r = requests.post(ep, data={"data": q},
                              headers={"User-Agent": "leadgen-engine/1.0"},
                              timeout=90)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                return r.json().get("elements", [])
            last_err = f"{ep} -> HTTP {r.status_code} {r.text[:80]}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{ep} -> {e}"
        wait = min(2 ** attempt * 5, 40)
        print(f"  deneme {attempt+1} başarısız ({last_err}) — {wait}s bekleniyor", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"Overpass erişilemedi: {last_err}")


def first(tags: dict, keys: list[str]) -> str:
    for k in keys:
        v = tags.get(k)
        if v:
            return str(v).strip()
    return ""


def addr(tags: dict) -> str:
    parts = [tags.get("addr:street", ""), tags.get("addr:housenumber", ""),
             tags.get("addr:city", ""), tags.get("addr:postcode", "")]
    return " ".join(p for p in parts if p).strip()


def to_leads(elements: list[dict], source_note: str) -> list[dict]:
    leads = []
    seen = set()
    for el in elements:
        t = el.get("tags", {})
        name = t.get("name", "").strip()
        if not name:
            continue
        email = first(t, EMAIL_KEYS)
        phone = first(t, TEL_KEYS)
        web = first(t, WEB_KEYS)
        key = (name.lower(), phone)
        if key in seen:
            continue
        seen.add(key)
        leads.append({
            "isletme": name,
            "kategori": t.get("amenity", ""),
            "telefon": phone,
            "website": web,
            "email": email,
            "adres": addr(t),
            "mutfak_detay": t.get("cuisine", ""),
            "calisma_saatleri": t.get("opening_hours", "")[:80],
            "ek_not": source_note,
            "iletisim_skoru": sum(bool(x) for x in (phone, web, email)),
        })
    leads.sort(key=lambda x: -x["iletisim_skoru"])
    return leads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default=None, help='Ör: "Kadıköy", "Çankaya"')
    ap.add_argument("--bbox", default=None, help="south,west,north,east")
    ap.add_argument("--types", default="cafe,restaurant,bar", help="virgülle amenity tipleri")
    ap.add_argument("--out", default="leads.csv")
    args = ap.parse_args()

    if not args.city and not args.bbox:
        ap.error("--city veya --bbox gerekli")

    types = [t.strip() for t in args.types.split(",") if t.strip()]
    print(f"Sorgu: bölge={args.city or args.bbox} tipler={types}")
    q = build_query(args.city, args.bbox, types)
    elements = query_overpass(q)
    leads = to_leads(elements, f"OSM/Overpass {time.strftime('%Y-%m-%d')}")

    out = Path(args.out)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(leads[0].keys()) if leads else ["isletme"])
        w.writeheader()
        w.writerows(leads)

    contactable = sum(1 for l in leads if l["iletisim_skoru"] >= 1)
    with_email = sum(1 for l in leads if l["email"])
    print(f"TAMAM: {len(leads)} işletme -> {out.resolve()}")
    print(f"  İletişim bilgisi olan: {contactable} | E-postası olan: {with_email}")


if __name__ == "__main__":
    main()
