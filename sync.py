#!/usr/bin/env python3
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://redecanaistv.app/"
CATALOG_URL = urljoin(BASE, "canais/")
OUTPUT = Path("public")
HEADERS = {"User-Agent": "redecanais-playlists-sync/1.0 (+https://github.com/projeto01rj-dotcom/redecanais-playlists)"}
LABELS = {
    "canais abertos": "Canais de TV", "documentarios": "Canais de TV",
    "entretenimento": "Canais de TV", "esportes": "Canais de TV",
    "noticias": "Canais de TV", "outros": "Canais de TV",
    "infantil": "Desenhos",
}

def norm(value):
    return re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower()).strip()

def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", norm(value)).strip("-") or "canal"

def esc(value):
    return str(value).replace('"', "&quot;").replace("\n", " ").strip()

def classify(item):
    category, name = norm(item.get("category")), norm(item.get("name"))
    text = f"{category} {name}"
    if category == "infantil":
        return "desenhos"
    if category == "filmes e series":
        film_channels = ("cinemax", "hbo family", "hbo pop", "hbo signature", "hbo xtreme", "hbo ", "megapix", "sony movies", "space", "studio universal", "telecine", "tnt")
        series_channels = ("amc", "axn", "canal brasil", "discovery id", "lifetime", "sony channel", "tnt novelas", "tnt series", "universal tv", "usa", "warner tv")
        if any(name == c.strip() or name.startswith(c) for c in film_channels):
            return "filmes"
        if any(name == c.strip() or name.startswith(c) for c in series_channels):
            return "series"
        return "series"
    cartoon_words = ("desenho", "cartoon", "toon", "gloob", "disney", "nick", "naruto", "dragon ball", "simpsons", "chaves", "tom e jerry", "bob esponja", "south park", "futurama", "family guy", "pica pau", "anime")
    return "desenhos" if any(word in text for word in cartoon_words) else "tv"

def get(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text

def direct_m3u8_urls(html, page_url):
    found = re.findall(r"https?[^\"'<>\\ ]+\.m3u8(?:\?[^\"'<>\\ ]*)?", html, flags=re.I)
    return list(dict.fromkeys(urljoin(page_url, value.replace("\\/", "/")) for value in found))

def collect():
    session = requests.Session()
    session.headers.update(HEADERS)
    catalog = get(session, CATALOG_URL)
    soup = BeautifulSoup(catalog, "html.parser")
    items, seen = [], set()
    for card in soup.select("[data-channel-card], article.channel-card"):
        link = card.select_one('a[href*="/canal/"]')
        if not link:
            continue
        page = urljoin(BASE, link.get("href"))
        if page in seen:
            continue
        seen.add(page)
        name = (card.get("data-name") or link.get("aria-label", "")).strip()
        name = re.sub(r"^Assistir\s+|\s+ao vivo$", "", name, flags=re.I).strip()
        image = card.select_one("img")
        logo = urljoin(BASE, image.get("src")) if image and image.get("src") else ""
        items.append({"name": name.title() or "Canal", "category": (card.get("data-category") or "outros").strip().lower(), "page": page, "logo": logo})
    for index, item in enumerate(items, 1):
        try:
            page_html = get(session, item["page"])
            page_soup = BeautifulSoup(page_html, "html.parser")
            if not item["logo"]:
                og = page_soup.select_one('meta[property="og:image"]')
                item["logo"] = og.get("content", "") if og else ""
            players = [urljoin(item["page"], iframe.get("src")) for iframe in page_soup.select("iframe[src]")]
            direct = direct_m3u8_urls(page_html, item["page"])
            # Fazer uma única camada adicional: alguns players deixam o manifesto no HTML do iframe.
            for player in players[:3]:
                try:
                    embedded_html = get(session, player)
                    direct.extend(direct_m3u8_urls(embedded_html, player))
                except requests.RequestException:
                    pass
            item["players"] = list(dict.fromkeys(players))
            item["m3u8"] = list(dict.fromkeys(direct))
            item["status"] = "ok"
        except requests.RequestException as error:
            item["players"], item["m3u8"] = [], []
            item["status"], item["error"] = "error", str(error)
        if index % 25 == 0:
            print(f"coletados {index}/{len(items)}", flush=True)
        time.sleep(0.05)
    return items

def build_playlists(items):
    buckets = {"tv": [], "desenhos": [], "filmes": [], "series": [], "players-fallback": []}
    for item in items:
        bucket = classify(item)
        # Cada canal permanece na sua categoria. O HLS direto tem prioridade;
        # quando não existe, a categoria recebe o player e o fallback também.
        direct_sources = item.get("m3u8") or []
        fallback_sources = item.get("players") or [] if not direct_sources else []
        sources = direct_sources or fallback_sources
        for option, source in enumerate(sources, 1):
            name = item.get("name") or "Canal"
            display = name if len(sources) == 1 else f"{name} (Opção {option})"
            page_slug = item.get("page", "").rstrip("/").split("/")[-1]
            channel_id = slug(page_slug or name) + (f"-opcao-{option}" if len(sources) > 1 else "")
            group = {"tv": "Canais de TV", "desenhos": "Desenhos", "filmes": "Filmes", "series": "Séries"}[bucket]
            attrs = [f'tvg-id="{esc(channel_id)}"', f'tvg-name="{esc(name)}"', f'group-title="{group}"']
            if item.get("logo"):
                attrs.append(f'tvg-logo="{esc(item["logo"])}"')
            block = f'#EXTINF:-1 {" ".join(attrs)},{esc(display)}\n{source}'
            buckets[bucket].append((name.casefold(), option, block))
            if fallback_sources:
                fallback_attrs = [f'tvg-id="{esc(channel_id)}"', f'tvg-name="{esc(name)}"', 'group-title="Players (fallback)"']
                if item.get("logo"):
                    fallback_attrs.append(f'tvg-logo="{esc(item["logo"])}"')
                buckets["players-fallback"].append((name.casefold(), option, f'#EXTINF:-1 {" ".join(fallback_attrs)},{esc(display)}\n{source}'))
    names = {"tv": "canais-tv.m3u8", "desenhos": "desenhos.m3u8", "filmes": "filmes.m3u8", "series": "series.m3u8", "players-fallback": "players-fallback.m3u8"}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    counts = {}
    for bucket, filename in names.items():
        entries = sorted(buckets[bucket], key=lambda row: (row[0], row[1]))
        lines = ["#EXTM3U", "#PLAYLIST-TYPE:VOD", "# Generated automatically from https://redecanaistv.app/", ""]
        for _, _, block in entries:
            lines.extend([block, ""])
        (OUTPUT / filename).write_text("\n".join(lines), encoding="utf-8")
        counts[filename] = len(entries)
    status = {
        "source": CATALOG_URL,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "channels_collected": len(items),
        "direct_m3u8_channels": sum(bool(item.get("m3u8")) for item in items),
        "embedded_player_channels": sum(bool(item.get("players")) and not bool(item.get("m3u8")) for item in items),
        "entries_by_file": counts,
        "errors": [item for item in items if item.get("status") != "ok"],
        "note": "A lista principal usa .m3u8 somente quando o manifesto é encontrado. Players incorporados ficam em players-fallback.m3u8.",
    }
    (OUTPUT / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "index.html").write_text("<!doctype html><meta charset='utf-8'><title>Playlists RedeCanaisTV</title><h1>Playlists</h1><ul>" + "".join(f"<li><a href='{name}'>{name}</a></li>" for name in names.values()) + "<li><a href='status.json'>status.json</a></li></ul>", encoding="utf-8")
    return counts

if __name__ == "__main__":
    data = collect()
    counts = build_playlists(data)
    print(json.dumps(counts, ensure_ascii=False))
    if not data:
        sys.exit("catálogo vazio")
