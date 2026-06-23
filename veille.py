#!/usr/bin/env python3
"""
Agent de veille technologique automatisee : cyber / IT / pharma.
Recupere des flux RSS, filtre sur une fenetre temporelle, puis genere
un digest synthetique en francais via l'API Anthropic.

Usage :
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 veille.py                 # fenetre par defaut (24h)
    python3 veille.py --hours 168     # bilan hebdomadaire (7 jours)
    python3 veille.py --no-llm        # collecte seule, sans synthese

Dependances :
    pip install feedparser anthropic
"""

import argparse
import datetime as dt
import os
import re
import sys
import time
from collections import defaultdict

import feedparser

# --------------------------------------------------------------------------- #
# CONFIGURATION                                                               #
# --------------------------------------------------------------------------- #

# Sources organisees par theme. Tous ces flux ont ete testes en acces machine.
SOURCES = {
    "Cyber": [
        ("CERT-FR (avis)",     "https://www.cert.ssi.gouv.fr/avis/feed/"),
        ("CERT-FR (alertes)",  "https://www.cert.ssi.gouv.fr/alerte/feed/"),
        ("CISA Advisories",    "https://www.cisa.gov/cybersecurity-advisories/all.xml"),
        ("BleepingComputer",   "https://www.bleepingcomputer.com/feed/"),
        ("The Hacker News",    "https://feeds.feedburner.com/TheHackersNews"),
        ("Krebs on Security",  "https://krebsonsecurity.com/feed/"),
        ("SANS ISC",           "https://isc.sans.edu/rssfeed.xml"),
        ("Dark Reading",       "https://www.darkreading.com/rss.xml"),
    ],
    "IT / Tech": [
        ("The Register",       "https://www.theregister.com/headlines.atom"),
        ("Hacker News",        "https://hnrss.org/frontpage"),
    ],
    "Pharma / Santé": [
        ("Fierce Pharma",      "https://www.fiercepharma.com/rss/xml"),
        ("Fierce Biotech",     "https://www.fiercebiotech.com/rss/xml"),
        ("Endpoints News",     "https://endpts.com/feed/"),
        ("STAT News",          "https://www.statnews.com/feed/"),
    ],
}

# Mots-cles de priorisation. Un item qui en contient un est marque [!].
# Laisser la liste vide pour ne rien prioriser.
KEYWORDS = [
    "vulnerability", "exploit", "zero-day", "ransomware", "cve", "patch",
    "breach", "data integrity", "fda", "ema", "gxp", "validation",
    "ai", "llm", "cloud", "supply chain",
]

MODEL = "claude-sonnet-4-6"   # synthese de qualite ; claude-haiku-4-5 pour reduire le cout
MAX_ITEMS_PER_THEME = 35      # plafond d'items envoyes au modele par theme
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 20                  # secondes par flux

# Regex de priorisation : recherche par mot entier (evite les faux positifs).
_KW_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in KEYWORDS) + r")\b",
                    re.IGNORECASE) if KEYWORDS else None

# --------------------------------------------------------------------------- #
# COLLECTE                                                                    #
# --------------------------------------------------------------------------- #

def _entry_date(entry):
    """Retourne la date de publication (aware UTC) ou None."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            return dt.datetime.fromtimestamp(time.mktime(parsed), tz=dt.timezone.utc)
    return None


def collect(window_hours):
    """Parcourt toutes les sources et retourne les items dans la fenetre."""
    cutoff = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=window_hours)
    items_by_theme = defaultdict(list)
    seen = set()

    for theme, feeds in SOURCES.items():
        for source_name, url in feeds:
            try:
                feed = feedparser.parse(url, agent=USER_AGENT)
            except Exception as exc:                       # reseau, parsing...
                print(f"  ! {source_name} : echec ({exc})", file=sys.stderr)
                continue
            if getattr(feed, "status", 200) >= 400 and not feed.entries:
                print(f"  ! {source_name} : HTTP {feed.status}", file=sys.stderr)
                continue

            kept = 0
            for entry in feed.entries:
                date = _entry_date(entry)
                if date is not None and date < cutoff:
                    continue                               # hors fenetre
                link = entry.get("link", "")
                title = entry.get("title", "(sans titre)").strip()
                dedup_key = link or title
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                summary = entry.get("summary", "").strip()
                blob = title + " " + summary
                priority = bool(_KW_RE.search(blob)) if _KW_RE else False
                items_by_theme[theme].append({
                    "source": source_name,
                    "title": title,
                    "link": link,
                    "date": date,
                    "summary": summary[:400],
                    "priority": priority,
                })
                kept += 1
            print(f"  - {source_name:20} {kept} item(s)", file=sys.stderr)

    # tri : prioritaires d'abord, puis par date decroissante
    for theme in items_by_theme:
        items_by_theme[theme].sort(
            key=lambda x: (x["priority"], x["date"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc)),
            reverse=True,
        )
    return items_by_theme

# --------------------------------------------------------------------------- #
# SYNTHESE                                                                    #
# --------------------------------------------------------------------------- #

def build_prompt(items_by_theme):
    lines = []
    for theme, items in items_by_theme.items():
        lines.append(f"\n## {theme}")
        for it in items[:MAX_ITEMS_PER_THEME]:
            flag = "[!] " if it["priority"] else ""
            d = it["date"].strftime("%d/%m") if it["date"] else "??/??"
            lines.append(f"- {flag}({it['source']}, {d}) {it['title']} | {it['link']}")
    corpus = "\n".join(lines)

    return (
        "Tu es analyste de veille pour un Digital Technical Expert dans un grand "
        "groupe pharmaceutique. Voici la collecte brute des dernieres heures, "
        "regroupee par theme.\n\n"
        f"{corpus}\n\n"
        "Produis un digest en francais, structure par theme. Pour chaque theme, "
        "selectionne uniquement les 4 a 6 items les plus pertinents pour un expert "
        "technique en pharma (priorise securite exploitable, conformite GxP/FDA/EMA, "
        "et innovations IT applicables). Pour chaque item retenu : une phrase de "
        "synthese + une phrase sur l'impact concret. Conserve le lien. Termine par "
        "une section 'A surveiller' de 3 points maximum. Sois factuel et concis, "
        "sans introduction ni conclusion superflue."
    )


def synthesize(items_by_theme):
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("Module 'anthropic' manquant : pip install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Variable ANTHROPIC_API_KEY absente.")

    client = Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        messages=[{"role": "user", "content": build_prompt(items_by_theme)}],
    )
    return "".join(block.text for block in message.content if block.type == "text")

# --------------------------------------------------------------------------- #
# SORTIE                                                                      #
# --------------------------------------------------------------------------- #

def raw_appendix(items_by_theme):
    lines = ["\n---\n\n## Annexe : collecte brute\n"]
    for theme, items in items_by_theme.items():
        lines.append(f"\n### {theme}")
        for it in items:
            flag = "**[priorité]** " if it["priority"] else ""
            lines.append(f"- {flag}[{it['title']}]({it['link']}) — {it['source']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Agent de veille cyber / IT / pharma")
    parser.add_argument("--hours", type=int, default=24,
                        help="fenetre de collecte en heures (def. 24 ; 168 = hebdo)")
    parser.add_argument("--no-llm", action="store_true",
                        help="collecte seule, sans synthese LLM")
    parser.add_argument("--out", default=None, help="chemin du rapport Markdown")
    args = parser.parse_args()

    print("Collecte des flux...", file=sys.stderr)
    items_by_theme = collect(args.hours)
    total = sum(len(v) for v in items_by_theme.values())
    print(f"Total : {total} item(s) sur {args.hours} h.", file=sys.stderr)

    today = dt.date.today().isoformat()
    header = (f"# Veille tech — {today}\n\n"
              f"Fenetre : {args.hours} h · {total} items collectes\n")

    if args.no_llm or total == 0:
        body = ""
    else:
        print("Synthese en cours...", file=sys.stderr)
        body = "\n" + synthesize(items_by_theme) + "\n"

    report = header + body + raw_appendix(items_by_theme)
    out_path = args.out or f"veille_{today}.md"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"Rapport ecrit : {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
