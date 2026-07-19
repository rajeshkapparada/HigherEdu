"""
zoho_sync.py — One-shot DB → Zoho CRM sync
-------------------------------------------
HOW IT WORKS:
  1. Connects to PostgreSQL and fetches every student row.
  2. Converts each student into a Zoho Lead dict (first/last name split,
     phone, country, study level, course all as proper CRM fields).
  3. Sends them in batches of 100 (Zoho's max per request) using the
     /Leads/upsert endpoint with duplicate_check_fields=["Email"] —
     so existing leads are UPDATED, not duplicated.
  4. Prints a colour-coded summary: created / updated / error per batch.

RUN:
  python zoho_sync.py
"""

import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import zoho_crm

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('zoho_sync_log.txt', encoding='utf-8'),
    ]
)
log = logging.getLogger(__name__)

BATCH_SIZE = 100   # Zoho allows max 100 records per upsert call


def fetch_all_students():
    """Pull every student from the DB."""
    conn = db.get_connection()
    cur  = conn.cursor()
    cur.execute('''
        SELECT id, name, email, student_id, study_level, country, course,
               image_path, phone, created_at
        FROM   students
        ORDER  BY id ASC
    ''')
    rows = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return rows


def student_to_lead(row):
    """Convert a DB student row into a Zoho Lead dict."""
    # row indices: id[0] name[1] email[2] student_id[3] study_level[4]
    #              country[5] course[6] image_path[7] phone[8] created_at[9]
    name        = (row[1] or '').strip()
    email       = (row[2] or '').strip()
    study_level = (row[4] or '')
    country     = (row[5] or '')
    course      = (row[6] or '')
    phone       = (row[8] or '')

    parts      = name.split(' ', 1)
    first_name = parts[0] if len(parts) > 1 else ''
    last_name  = parts[-1] if name else 'Unknown'

    return {
        'First_Name':  first_name,
        'Last_Name':   last_name,
        'Email':       email,
        'Phone':       phone,
        'Lead_Source': 'Web Site',
        'Country':     country,
        'Description': (
            f'Study Level: {study_level} | '
            f'Course: {course} | '
            f'Preferred Country: {country}'
        ),
    }


def upsert_batch(leads, access_token):
    """Send one batch of up to 100 leads to Zoho using the upsert endpoint.
    duplicate_check_fields=Email means Zoho will UPDATE existing leads
    instead of creating duplicates."""
    import requests
    resp = requests.post(
        f'{zoho_crm.API_URL}/crm/v2/Leads/upsert',
        headers={
            'Authorization': f'Zoho-oauthtoken {access_token}',
            'Content-Type':  'application/json',
        },
        json={
            'data':                   leads,
            'duplicate_check_fields': ['Email'],
        },
        timeout=30,
    )
    return resp.json()


def parse_batch_result(result):
    """Count created / updated / error from a Zoho upsert response."""
    created = updated = errors = 0
    for item in result.get('data', []):
        status = item.get('status', '')
        action = item.get('action', '')
        code   = item.get('code', '')
        if code != 'SUCCESS':
            errors += 1
            log.warning(f'  ERROR — {item.get("message", "unknown")}  details: {item}')
        elif action == 'insert':
            created += 1
        elif action == 'update':
            updated += 1
    return created, updated, errors


def run():
    log.info('=' * 60)
    log.info('HigherEDU → Zoho CRM Sync')
    log.info('=' * 60)

    # ── Step 1: fetch students ────────────────────────────────────
    log.info('STEP 1 — Fetching students from PostgreSQL...')
    students = fetch_all_students()
    log.info(f'  Found {len(students)} student(s) in the database.')

    if not students:
        log.info('  Nothing to sync. Exiting.')
        return

    # ── Step 2: get a fresh Zoho access token ────────────────────
    log.info('STEP 2 — Obtaining Zoho access token...')
    try:
        access_token = zoho_crm._get_access_token()
        log.info('  Token obtained successfully.')
    except Exception as e:
        log.error(f'  FAILED to get Zoho token: {e}')
        log.error('  Make sure you have authorised Zoho by visiting /zoho/auth first.')
        sys.exit(1)

    # ── Step 3: convert all students to Zoho Lead dicts ──────────
    log.info('STEP 3 — Converting student records to Zoho Lead format...')
    leads = [student_to_lead(s) for s in students]
    log.info(f'  {len(leads)} lead(s) ready to sync.')

    # ── Step 4: batch upsert ─────────────────────────────────────
    log.info(f'STEP 4 — Upserting in batches of {BATCH_SIZE}...')
    log.info('         (duplicate_check_fields=Email — existing leads will be')
    log.info('          UPDATED, new ones will be CREATED — no duplicates)')
    log.info('-' * 60)

    total_created = total_updated = total_errors = 0
    batches = [leads[i:i + BATCH_SIZE] for i in range(0, len(leads), BATCH_SIZE)]

    for idx, batch in enumerate(batches, 1):
        log.info(f'  Batch {idx}/{len(batches)} — sending {len(batch)} records...')
        try:
            result  = upsert_batch(batch, access_token)
            c, u, e = parse_batch_result(result)
            total_created += c
            total_updated += u
            total_errors  += e
            log.info(f'    Created: {c}  |  Updated: {u}  |  Errors: {e}')
        except Exception as ex:
            log.error(f'    Batch {idx} request failed: {ex}')
            total_errors += len(batch)

        # Zoho rate limit: 10 API calls/min on free plans — pause between batches
        if idx < len(batches):
            time.sleep(1.5)

    # ── Step 5: summary ──────────────────────────────────────────
    log.info('=' * 60)
    log.info('SYNC COMPLETE')
    log.info(f'  Total students : {len(students)}')
    log.info(f'  Created in CRM : {total_created}')
    log.info(f'  Updated in CRM : {total_updated}')
    log.info(f'  Errors         : {total_errors}')
    log.info('  Full log saved to zoho_sync_log.txt')
    log.info('=' * 60)


if __name__ == '__main__':
    run()
