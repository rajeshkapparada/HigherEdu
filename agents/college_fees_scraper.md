---
title: College Fees Scraper
description: Automated agent that scrapes college/university websites weekly and updates the database with the latest fees and course details
model: claude-sonnet-4-6
---

## Overview
This agent runs once every week, visits each college website stored in the database, scrapes the latest tuition fees and course information, compares it with the existing data, and updates the database if any changes are found.

---

## Purpose
- Automatically keep college fees and course data up to date
- Detect fee changes, new courses, or removed courses on university portals
- Update the database without any manual work
- Notify the admin if a significant change is detected

---

## How It Works

1. **Fetch** — Read all colleges from the database (name, website URL)
2. **Scrape** — Visit each college website and extract tuition fees, course names, and course levels
3. **Compare** — Compare the scraped data with the current data in the database
4. **Update** — If a change is found, update the database with the new values
5. **Log** — Record what changed, what stayed the same, and any errors
6. **Notify** — Send a summary report to the admin (email or dashboard)

---

## Schedule
- Runs **every Monday at 12:00 AM**
- Triggered by Windows Task Scheduler (or a cron job on Linux)

---

## Inputs
| Input | Source | Description |
|-------|--------|-------------|
| College list | Database (`colleges` table) | Name and website URL of each college |
| Existing fees | Database (`colleges.tuition_fee_usd`) | Current fee stored in the database |
| Existing courses | Database (`courses` table) | Current courses stored in the database |

---

## Outputs
| Output | Description |
|--------|-------------|
| Updated database | New fees and course details written to the database |
| Change log | A log file recording every change made |
| Admin report | Summary of changes detected (email or dashboard message) |

---

## Technologies Used
| Tool | Purpose |
|------|---------|
| Python | Main scripting language |
| BeautifulSoup | Scraping static HTML pages |
| Selenium | Scraping dynamic/JavaScript-heavy pages |
| psycopg2 | Connecting to PostgreSQL database |
| schedule / Task Scheduler | Running the agent weekly |
| smtplib | Sending email notifications to admin |

---

## Files
```
agents/
  college_fees_scraper.md       ← this document
  college_fees_scraper.py       ← main scraper script
  scraper_log.txt               ← log of all changes
```

---

## Error Handling
- If a college website is **unreachable** — skip it, log the error, try again next week
- If scraping **fails** (page layout changed) — log the error, do not update the database, alert admin
- If the database **update fails** — roll back the change, log the error

---

## Example Log Entry
```
[2026-07-14 00:01:32] MIT — Tuition fee changed: $55,000 → $57,500
[2026-07-14 00:02:10] Oxford — No changes found
[2026-07-14 00:03:45] Harvard — ERROR: Website unreachable, skipping
[2026-07-14 00:04:20] NUS — New course added: MSc Data Science
```

---

## Future Improvements
- Add support for scraping scholarship deadlines
- Send WhatsApp notification to admin on major fee changes
- Show change history to students on the dashboard
