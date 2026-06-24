#!/usr/bin/env python3
"""
Genere un flux RSS (docs/feed.xml) et une page d'accueil (docs/index.html)
a partir des rapports presents dans reports/veille_*.md, en vue d'une
publication via GitHub Pages.

Usage :
    FEED_SITE_URL="https://utilisateur.github.io/veille-tech" python3 make_feed.py

Dependance : pip install markdown
"""

import datetime as dt
import glob
import html
import os
import re

try:
    import markdown  # rendu Markdown -> HTML
except ImportError:                       # repli si la lib n'est pas installee
    markdown = None

# --------------------------------------------------------------------------- #
# CONFIGURATION                                                               #
# --------------------------------------------------------------------------- #

SITE_URL = os.environ.get("FEED_SITE_URL", "").rstrip("/")
TITLE = "Veille tech (cyber / IT / pharma)"
DESCRIPTION = "Digest quotidien de veille technologique, genere automatiquement."
LANGUAGE = "fr"
MAX_ITEMS = 30                 # nombre de digests exposes dans le flux
REPORTS_DIR = "reports"
OUT_DIR = "docs"

_DATE_RE = re.compile(r"veille_(\d{4}-\d{2}-\d{2})\.md$")


def md_to_html(text):
    """Convertit du Markdown en HTML (repli minimal si la lib est absente)."""
    if markdown is not None:
        return markdown.markdown(text, extensions=["extra", "sane_lists"])
    return "<pre>" + html.escape(text) + "</pre>"


def rfc822(date):
    """Date RFC-822 (format attendu par RSS), en UTC."""
    return date.strftime("%a, %d %b %Y %H:%M:%S +0000")


def collect_reports():
    """Retourne [(date_str, chemin), ...] tries du plus recent au plus ancien."""
    found = []
    for path in glob.glob(os.path.join(REPORTS_DIR, "veille_*.md")):
        match = _DATE_RE.search(path)
        if match:
            found.append((match.group(1), path))
    found.sort(reverse=True)
    return found[:MAX_ITEMS]


def build(reports):
    now = dt.datetime.now(tz=dt.timezone.utc)
    items_xml, index_sections = [], []

    for date_str, path in reports:
        with open(path, encoding="utf-8") as fh:
            content_html = md_to_html(fh.read())
        date = dt.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        item_title = f"Veille tech — {date_str}"
        anchor = f"veille-{date_str}"
        link = f"{SITE_URL}/#{anchor}" if SITE_URL else f"#{anchor}"

        items_xml.append(
            "    <item>\n"
            f"      <title>{html.escape(item_title)}</title>\n"
            f"      <link>{html.escape(link)}</link>\n"
            f'      <guid isPermaLink="false">{html.escape(anchor)}</guid>\n'
            f"      <pubDate>{rfc822(date)}</pubDate>\n"
            f"      <description><![CDATA[{content_html}]]></description>\n"
            "    </item>"
        )
        index_sections.append(
            f'<section id="{anchor}">\n<h2>{html.escape(item_title)}</h2>\n'
            f"{content_html}\n</section>"
        )

    self_link = f'<atom:link href="{html.escape(SITE_URL)}/feed.xml" rel="self" type="application/rss+xml" />\n    ' if SITE_URL else ""
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{html.escape(TITLE)}</title>\n"
        f"    <link>{html.escape(SITE_URL or 'about:blank')}</link>\n"
        f"    <description>{html.escape(DESCRIPTION)}</description>\n"
        f"    <language>{LANGUAGE}</language>\n"
        f"    <lastBuildDate>{rfc822(now)}</lastBuildDate>\n"
        f"    {self_link}"
        + "\n".join(items_xml) + "\n"
        "  </channel>\n"
        "</rss>\n"
    )

    index = (
        "<!doctype html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(TITLE)}</title>\n"
        f'<link rel="alternate" type="application/rss+xml" title="{html.escape(TITLE)}" href="feed.xml">\n'
        "<style>body{font-family:system-ui,-apple-system,sans-serif;max-width:780px;"
        "margin:2rem auto;padding:0 1rem;line-height:1.55;color:#1a1a1a}"
        "h1{margin-bottom:.2rem}section{border-top:1px solid #e2e2e2;margin-top:2.5rem;"
        "padding-top:1rem}a{color:#0969da}code{background:#f3f3f3;padding:.1em .3em;"
        "border-radius:4px}</style>\n</head>\n<body>\n"
        f"<h1>{html.escape(TITLE)}</h1>\n"
        f'<p>Flux RSS : <a href="feed.xml">feed.xml</a></p>\n'
        + "\n".join(index_sections)
        + "\n</body>\n</html>\n"
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "feed.xml"), "w", encoding="utf-8") as fh:
        fh.write(feed)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index)
    # Empeche GitHub Pages d'appliquer Jekyll (qui ignorerait certains fichiers).
    open(os.path.join(OUT_DIR, ".nojekyll"), "w").close()

    print(f"Flux genere : {len(reports)} item(s) -> {OUT_DIR}/feed.xml")


if __name__ == "__main__":
    reports = collect_reports()
    if not reports:
        print("Aucun rapport trouve dans reports/ ; flux non genere.")
    else:
        build(reports)
