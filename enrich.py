#!/usr/bin/env python3
"""
Zenginleştirme motoru — websitsi olan işletmelerin ana sayfasını tarayıp
e-posta/telefon bilgisi çıkarır (Gmail/Telif sayfalarını da kontrol eder).

Kullanım: python enrich.py --in leads.csv --out leads_zengin.csv [--limit 100] [--delay 1.0]
"""
import argparse
import asyncio
import re
import sys
import csv
from pathlib import Path

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+90|0)\s?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}")
BAD_EMAIL = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", "example.com", "sentry", "wixpress",
             "@2x", "@3x", "email@", "@domain", "godaddy", "w3.org", "schema.org")
CONTACT_PATHS = ["/iletisim", "/contact", "/contact-us", "/iletisim.html", "/hakkimizda"]


def emails_from(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            found.add(href[7:].split("?")[0].strip())
        elif href.startswith("tel:"):
            continue
    text = soup.get_text(" ", strip=True)
    for e in EMAIL_RE.findall(text):
        found.add(e)
    clean = [e.lower() for e in found
             if not any(b in e.lower() for b in BAD_EMAIL) and not re.match(r"^\d+@", e)]
    return clean


def phones_from(html: str) -> list[str]:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return [re.sub(r"\s+", " ", p).strip() for p in PHONE_RE.findall(text)]


async def enrich_row(crawler: AsyncWebCrawler, row: dict, semaphore) -> dict:
    site = row.get("website", "").strip()
    if not site.startswith("http"):
        site = "https://" + site if site else ""
    async with semaphore:
        for path in [""] + CONTACT_PATHS:
            if not site:
                break
            url = site + path
            try:
                r = await crawler.arun(url=url)
            except Exception:
                continue
            if not r.success:
                continue
            html = r.cleaned_html or r.html or ""
            new_emails = emails_from(html)
            new_phones = phones_from(html)
            if new_emails or new_phones:
                if not row.get("email") and new_emails:
                    row["email"] = new_emails[0]
                if not row.get("telefon") and new_phones:
                    row["telefon"] = new_phones[0]
                row["zenginlastirme_kaynagi"] = url
                break
    return row


async def main(args):
    rows = list(csv.DictReader(open(args.input, encoding="utf-8-sig")))
    todo = [r for r in rows if r.get("website") and not r.get("email")]
    todo = todo[: args.limit]
    print(f"{len(rows)} kayıttan {len(todo)} tanesi zenginleştirilecek", file=sys.stderr)
    crawler = AsyncWebCrawler()
    await crawler.start()
    sem = asyncio.Semaphore(5)
    enriched = await asyncio.gather(*[enrich_row(crawler, r, sem) for r in todo])
    await crawler.close()

    for r in enriched:
        r["iletisim_skoru"] = sum(bool(r.get(k)) for k in ("telefon", "website", "email"))
    out = Path(args.out)
    fieldnames = list(rows[0].keys())
    for extra in ("zenginlastirme_kaynagi",):
        if extra not in fieldnames:
            fieldnames.append(extra)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    with_email = sum(1 for r in rows if r.get("email"))
    print(f"TAMAM: {len(rows)} kayıt | e-postalı: {with_email} (+{sum(1 for r in enriched if r.get('email'))} yeni) -> {out.resolve()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="input", required=True)
    ap.add_argument("--out", default="leads_zengin.csv")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--delay", type=float, default=0.5)
    a = ap.parse_args()
    asyncio.run(main(a))
