import os
import re
import json
import logging
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# Add parent folder so we can import db.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

# ── Logging setup ──────────────────────────────────────────────────────────────
log_file = os.path.join(os.path.dirname(__file__), 'scraper_log.txt')
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

# ── Grok API client ────────────────────────────────────────────────────────────
GROK_API_KEY = os.environ.get('GROK_API_KEY')
if not GROK_API_KEY:
    log.error('GROK_API_KEY not set. Add it to your .env file.')
    sys.exit(1)

grok = OpenAI(
    api_key=GROK_API_KEY,
    base_url='https://api.x.ai/v1',
)


# ── Step 1: Fetch webpage HTML ─────────────────────────────────────────────────

def fetch_page(url):
    if not url.startswith('http'):
        url = 'https://' + url
    try:
        resp = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; HigherEduBot/1.0)'
        })
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        log.error(f'Cannot reach website: {url} — {e}')
        return None


# ── Step 2: Extract fees using Grok AI ────────────────────────────────────────

def extract_fee_with_grok(html, college_name):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    text = soup.get_text(separator=' ', strip=True)[:5000]

    try:
        response = grok.chat.completions.create(
            model='grok-2-1212',
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a data extraction assistant. '
                        'Extract tuition fee information from university website text. '
                        'Always respond with valid JSON only, no extra text.'
                    )
                },
                {
                    'role': 'user',
                    'content': (
                        f'Extract the annual international tuition fee for {college_name}.\n'
                        'Return ONLY this JSON (no markdown, no explanation):\n'
                        '{"tuition_fee_usd": <integer or null>, "notes": "<short note>"}\n\n'
                        f'Website text:\n{text}'
                    )
                }
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'```json|```', '', raw).strip()
        return json.loads(raw)
    except Exception as e:
        log.error(f'Grok failed for {college_name}: {e}')
        return None


# ── Step 3: Database helpers ───────────────────────────────────────────────────

def get_all_colleges():
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT id, name, website, tuition_fee_usd
        FROM   colleges
        WHERE  website IS NOT NULL
        ORDER  BY name
    ''')
    rows = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return rows


def update_fee(college_id, new_fee):
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('UPDATE colleges SET tuition_fee_usd = %s WHERE id = %s', (new_fee, college_id))
    conn.commit()
    cur.close()
    db.release_connection(conn)


# ── Step 4: Main scraper ───────────────────────────────────────────────────────

def run():
    log.info('=' * 65)
    log.info(f'College Fees Scraper started — {datetime.now().strftime("%A, %d %B %Y")}')
    log.info('=' * 65)

    colleges = get_all_colleges()
    log.info(f'Total colleges to check: {len(colleges)}')
    log.info('-' * 65)

    changed   = 0
    unchanged = 0
    failed    = 0

    for college_id, name, website, current_fee in colleges:
        log.info(f'Checking: {name}')

        # 1. Fetch the page
        html = fetch_page(website)
        if not html:
            log.warning(f'  SKIPPED — website unreachable')
            failed += 1
            continue

        # 2. Ask Grok to extract the fee
        result = extract_fee_with_grok(html, name)
        if not result or result.get('tuition_fee_usd') is None:
            log.warning(f'  SKIPPED — could not extract fee from page')
            failed += 1
            continue

        new_fee = int(result['tuition_fee_usd'])
        notes   = result.get('notes', '')

        # 3. Compare and update
        if current_fee != new_fee:
            old = f'${current_fee:,}' if current_fee else 'N/A'
            log.info(f'  UPDATED — {old} → ${new_fee:,}  ({notes})')
            update_fee(college_id, new_fee)
            changed += 1
        else:
            log.info(f'  NO CHANGE — ${current_fee:,}')
            unchanged += 1

    # 4. Summary
    log.info('=' * 65)
    log.info(f'DONE — Updated: {changed} | No change: {unchanged} | Failed: {failed}')
    log.info('=' * 65)


if __name__ == '__main__':
    run()
