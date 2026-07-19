#!/usr/bin/env python3
"""
Web scraper — fetches university listings from Wikipedia for the 10 countries
supported by HigherEDU, then saves new entries to the student_portal database
alongside representative courses.

Usage:
    python scraper.py              # scrape all 10 countries
    python scraper.py --dry-run    # print what would be inserted, no DB writes
    python scraper.py "Canada"     # scrape a single country by name
"""

import os
import re
import sys
import time
import psycopg2
from dotenv import load_dotenv

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Missing dependencies. Run:  pip install requests beautifulsoup4")
    sys.exit(1)

load_dotenv()

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'student_portal'),
    'user':     os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD'),
    'port':     os.environ.get('DB_PORT', '5432'),
}

# Wikipedia page title for each country's university list
WIKI_PAGES = {
    'United States':  'List_of_research_universities_in_the_United_States',
    'United Kingdom': 'List_of_universities_in_the_United_Kingdom',
    'Canada':         'List_of_universities_in_Canada',
    'Australia':      'List_of_universities_in_Australia',
    'Germany':        'List_of_universities_in_Germany',
    'Netherlands':    'List_of_universities_in_the_Netherlands',
    'New Zealand':    'List_of_universities_in_New_Zealand',
    'Ireland':        'List_of_universities_in_the_Republic_of_Ireland',
    'Sweden':         'List_of_universities_and_colleges_in_Sweden',
    'Switzerland':    'List_of_universities_in_Switzerland',
}

# Approximate annual tuition in USD for scraped universities by country
DEFAULT_TUITION = {
    'United States':  42000,
    'United Kingdom': 30000,
    'Canada':         22000,
    'Australia':      26000,
    'Germany':          200,
    'Netherlands':    14000,
    'New Zealand':    19000,
    'Ireland':        16000,
    'Sweden':         13000,
    'Switzerland':      900,
}

# Default state label when the city can't be detected from the page
DEFAULT_STATE = {
    'United States':  'Various States',
    'United Kingdom': 'England',
    'Canada':         'Various Provinces',
    'Australia':      'Various States',
    'Germany':        'Various States',
    'Netherlands':    'Various Provinces',
    'New Zealand':    'Various Regions',
    'Ireland':        'Leinster',
    'Sweden':         'Various Counties',
    'Switzerland':    'Various Cantons',
}

# Representative courses added for each scraped university
COURSES_BY_LEVEL = {
    'Bachelors': [
        ('BSc Computer Science',           '3-4 years'),
        ('BSc Software Engineering',       '4 years'),
        ('BSc Data Science & Analytics',   '3 years'),
        ('BA Business Administration',     '3 years'),
        ('BEng Engineering',               '4 years'),
        ('BSc Artificial Intelligence',    '3-4 years'),
    ],
    'Masters': [
        ('MSc Computer Science',           '1-2 years'),
        ('MSc Data Science & AI',          '1 year'),
        ('MSc Project Management',         '1 year'),
        ('MBA General Management',         '1-2 years'),
        ('MSc Cybersecurity',              '1 year'),
        ('MSc International Business',     '1 year'),
    ],
    'PhD': [
        ('PhD Computer Science',           '3-4 years'),
        ('PhD Engineering',                '3-4 years'),
        ('PhD Business & Management',      '3-4 years'),
        ('PhD Natural Sciences',           '3-4 years'),
    ],
    'Diploma': [
        ('Diploma in Data Analytics',      '6-12 months'),
        ('Diploma in Project Management',  '6-12 months'),
        ('Diploma in Information Technology', '1 year'),
    ],
}

# Keywords that indicate a line is a university name
_UNI_KEYWORDS = (
    'university', 'college', 'institute', 'school', 'polytechnic',
    'académie', 'hochschule', 'universität', 'universiteit',
    'università', 'université', 'escuela', 'iit', 'iim',
)

_REF_RE  = re.compile(r'\[\d+\]')          # footnote refs [1]
_PAREN_RE = re.compile(r'\s*\(.*?\)\s*')   # parenthetical notes (founded 1832)


def _clean(text: str) -> str:
    text = _REF_RE.sub('', text)
    text = _PAREN_RE.sub(' ', text)
    return text.strip().strip('†–—·')


def fetch_wiki_page(title: str) -> BeautifulSoup:
    url = f"https://en.wikipedia.org/wiki/{title}"
    headers = {'User-Agent': 'HigherEDU-Scraper/1.0 (educational research project)'}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, 'html.parser')


def extract_unis(soup: BeautifulSoup, country: str) -> list[tuple[str, str]]:
    """Return a list of (university_name, city) tuples parsed from the soup."""
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    # ── Strategy 1: wikitable rows ──────────────────────────────────────────
    for table in soup.find_all('table', class_=lambda c: c and 'wikitable' in c):
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
            name = _clean(cells[0].get_text(separator=' ', strip=True))
            if not name or len(name) < 8 or name.lower() in ('university', 'institution', 'name'):
                continue

            # Try columns 2 and 3 for a city
            city = DEFAULT_STATE.get(country, 'Unknown')
            for cell in cells[1:4]:
                txt = _clean(cell.get_text(separator=' ', strip=True))
                if txt and 3 < len(txt) < 60 and not txt.isdigit():
                    city = txt.split(',')[0].split('·')[0].strip()
                    break

            name = name[:200]
            if name not in seen:
                seen.add(name)
                results.append((name, city[:100]))

    # ── Strategy 2: bulleted list items ─────────────────────────────────────
    if len(results) < 10:
        for li in soup.find_all('li'):
            a = li.find('a')
            if not a:
                continue
            name = _clean(a.get_text(strip=True))
            if (8 < len(name) < 200
                    and any(kw in name.lower() for kw in _UNI_KEYWORDS)
                    and name not in seen):
                seen.add(name)
                results.append((name, DEFAULT_STATE.get(country, 'Unknown')))

    return results


# ── DB helpers ───────────────────────────────────────────────────────────────

def _get_or_create(cur, table: str, name_col: str, name: str, extra: dict = None) -> int:
    extra = extra or {}
    cols  = [name_col] + list(extra.keys())
    vals  = [name] + list(extra.values())
    where = f"{name_col} = %s" + ''.join(f' AND {k} = %s' for k in extra)
    cur.execute(f'SELECT id FROM {table} WHERE {where}', [name] + list(extra.values()))
    row = cur.fetchone()
    if row:
        return row[0]
    placeholders = ', '.join(['%s'] * len(vals))
    cur.execute(
        f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders}) RETURNING id', vals
    )
    return cur.fetchone()[0]


def insert_college(cur, name: str, city_id: int, tuition: int) -> int | None:
    cur.execute('SELECT id FROM colleges WHERE name = %s AND city_id = %s', (name, city_id))
    if cur.fetchone():
        return None
    cur.execute(
        'INSERT INTO colleges (name, description, website, city_id, tuition_fee_usd) '
        'VALUES (%s, %s, %s, %s, %s) RETURNING id',
        (name, 'Leading higher-education institution scraped from Wikipedia.', None, city_id, tuition)
    )
    return cur.fetchone()[0]


def seed_college_courses(cur, college_id: int, college_name: str) -> None:
    cur.execute('SELECT COUNT(*) FROM courses WHERE college_id = %s', (college_id,))
    if cur.fetchone()[0] > 0:
        return

    name_l = college_name.lower()
    postgrad_only = ('karolinska', 'london school of economics')
    no_phd        = ('eastern institute', 'unitec', 'malmö', 'technological university dublin',
                     'munster tech', 'south east tech', 'dublin city university')

    levels = ['Masters', 'Diploma']
    if not any(k in name_l for k in postgrad_only):
        levels = ['Bachelors'] + levels
    if not any(k in name_l for k in no_phd):
        levels.append('PhD')

    for level in levels:
        for cname, duration in COURSES_BY_LEVEL[level]:
            cur.execute(
                'INSERT INTO courses (name, level, currency, duration, description, college_id) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                (cname, level, 'USD', duration,
                 f'{level} programme in {cname.split()[-1]}.', college_id)
            )


# ── Main scraper ─────────────────────────────────────────────────────────────

def run(countries: list[str] | None = None, dry_run: bool = False) -> None:
    targets = {k: v for k, v in WIKI_PAGES.items()
               if countries is None or k in countries}

    if not targets:
        print("No matching countries found. Check the country name(s) you passed.")
        return

    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    total_new = 0

    for country, wiki_title in targets.items():
        print(f"\n{'='*64}")
        print(f"  {country}  ({wiki_title})")
        print(f"{'='*64}")

        try:
            soup = fetch_wiki_page(wiki_title)
        except Exception as exc:
            print(f"  [ERROR] Could not fetch Wikipedia page: {exc}")
            continue

        unis = extract_unis(soup, country)
        print(f"  Parsed {len(unis)} entries from Wikipedia")

        if dry_run:
            for name, city in unis[:20]:
                print(f"  [DRY-RUN]  {name[:70]}  ({city})")
            if len(unis) > 20:
                print(f"  ... and {len(unis)-20} more (truncated)")
            continue

        country_id  = _get_or_create(cur, 'countries', 'name', country)
        default_st  = DEFAULT_STATE.get(country, 'Various')
        state_id    = _get_or_create(cur, 'states', 'name', default_st,
                                     {'country_id': country_id})
        tuition     = DEFAULT_TUITION.get(country, 20000)
        added       = 0

        for name, city in unis[:100]:   # cap at 100 per country
            if len(name) < 8 or len(name) > 200:
                continue
            city_id    = _get_or_create(cur, 'cities', 'name', city[:100],
                                        {'state_id': state_id})
            college_id = insert_college(cur, name, city_id, tuition)
            if college_id:
                seed_college_courses(cur, college_id, name)
                added += 1

        conn.commit()
        print(f"  Inserted {added} new universities for {country}")
        total_new += added
        time.sleep(1.2)   # polite crawl delay

    cur.close()
    conn.close()

    print(f"\n{'='*64}")
    if dry_run:
        print("  Dry-run complete — no rows written.")
    else:
        print(f"  Done!  Total new universities added: {total_new}")


if __name__ == '__main__':
    args      = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry_run   = '--dry-run' in sys.argv
    countries = args if args else None
    run(countries=countries, dry_run=dry_run)
