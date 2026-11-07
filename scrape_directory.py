#!/usr/bin/env python3
"""
LeadGen Engine — dizin sitelerinden işletme/müşteri verisi toplar.
Kullanım: python scrape.py --config config.json
Çıktı: leads.csv (adi, website, email, telefon, adres, kaynak)
"""
import argparse
import asyncio
import csv
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+90|0)?\s?\(?5\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}")
PHONE_INTL_RE = re.compile(r"\+\d{1,3}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3}[\s.-]?\d{2,4}")


def extract_leads(html: str, selectors: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    container_sel = selectors.get("container")
    name_sel = selectors.get("name")
    items = soup.select(container_sel) if container_sel else [soup]

    leads = []
    for item in items:
        text = item.get_text(" ", strip=True)
        name = ""
        if name_sel:
            el = item.select_one(name_sel)
            name = el.get_text(strip=True) if el else ""
        emails = EMAIL_RE.findall(item.get("href", "") + " " + text)
        phones = PHONE_RE.findall(text) + PHONE_INTL_RE.findall(text)
        website = ""
        link = item.find("a", href=True)
        if link:
            href = link["href"]
            website = href if href.startswith("http") else ""
        if name or emails or phones:
            leads.append({
                "name": name[:120],
                "website": website[:200],
                "email": emails[0][:120] if emails else "",
                "phone": phones[0].strip() if phones else "",
                "raw_text_snippet": text[:200],
            })
    return leads


async def scrape(url: str, selectors: dict, max_pages: int, link_pattern: str | None) -> list[dict]:
    all_leads = []
    async with AsyncWebCrawler() as crawler:
        # 1) Listeleme/ana sayfa
        result = await crawler.arun(url=url)
        if not result.success:
            print(f"HATA: {url} çekilemedi", file=sys.stderr)
            return []
        all_leads.extend(extract_leads(result.cleaned_html or result.html, selectors))

        # 2) Alt sayfalar (pagination) — link_pattern regex ile eşleşen linkleri takip et
        if link_pattern and max_pages > 1:
            soup = BeautifulSoup(result.cleaned_html or result.html, "html.parser")
            urls = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if re.search(link_pattern, href):
                    full = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
                    if full not in urls and full != url:
                        urls.append(full)
            for u in urls[: max_pages - 1]:
                r = await crawler.arun(url=u)
                if r.success:
                    all_leads.extend(extract_leads(r.cleaned_html or r.html, selectors))
    return all_leads


def dedupe(leads: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for l in leads:
        key = (l["name"].lower(), l["email"].lower(), l["phone"])
        if key in seen or (not l["name"] and not l["email"] and not l["phone"]):
            continue
        seen.add(key)
        out.append(l)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    leads = asyncio.run(scrape(cfg["url"], cfg.get("selectors", {}), cfg.get("max_pages", 1), cfg.get("link_pattern")))
    leads = dedupe(leads)

    out = Path(cfg.get("output", "leads.csv"))
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "website", "email", "phone", "raw_text_snippet"])
        w.writeheader()
        w.writerows(leads)

    print(f"TAMAM: {len(leads)} lead -> {out.resolve()}")


if __name__ == "__main__":
    main()
