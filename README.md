# HigherEDU — Study Abroad Student Portal

A Flask web application that helps students discover universities abroad, register their study preferences, and explore colleges by destination country.

## Features

- **Student portal** — register, log in, and view a personalised dashboard of universities in the student's preferred country
- **University directory** — 100 pre-seeded universities across 10 top study-abroad destinations, with ranking, tuition fees, and scholarship information
- **Country tiles** — browse all available destinations from the dashboard and fetch universities per country via AJAX
- **Profile photo upload** — students can upload a profile image (PNG/JPG) during registration
- **REST API** — JSON endpoints for all student operations (register, login, profile, CRUD)
- **Developer panel** — password-protected admin UI at `/dev` to manage students, countries, states, cities, colleges, and courses

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask 3.1 |
| Database | PostgreSQL (psycopg2 with connection pooling) |
| Auth | Werkzeug password hashing |
| Frontend | Jinja2 templates, custom CSS, Google Fonts |
| Config | python-dotenv |
| Production server | Gunicorn |

## Project Structure

```
HigherEdu/
├── app.py              # Flask routes (student portal + dev panel + REST API)
├── db.py               # DB connection pool, table creation, seed data
├── requirements.txt
├── .env                # DB credentials (not committed)
├── static/
│   ├── style.css
│   ├── app.js
│   └── upload/         # uploaded profile images
└── templates/
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── dev_login.html
    ├── dev_dashboard.html
    ├── dev_edit.html
    ├── dev_countries.html
    ├── dev_states.html
    ├── dev_cities.html
    ├── dev_colleges.html
    ├── dev_edit_college.html
    ├── dev_courses.html
    └── dev_edit_course.html
```

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL running locally (or a remote server)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```
DB_HOST=localhost
DB_NAME=student_portal
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432
SECRET_KEY=your_secret_key
```

### 3. Create the database

```sql
CREATE DATABASE student_portal;
```

### 4. Run the application

```bash
python app.py
```

On first run, all tables are created automatically and the database is seeded with 100 universities across 10 countries.

The app starts at `http://127.0.0.1:5000`.

## Default Credentials

| Role | Username / Email | Password |
|---|---|---|
| Developer / Admin | `devadmin` | `Dev@1234` |

## Web Routes

| Route | Description |
|---|---|
| `/` or `/login` | Student login |
| `/register` | Student registration |
| `/dashboard` | Student dashboard (login required) |
| `/logout` | Clear student session |
| `/dev` or `/dev/login` | Developer panel login |
| `/dev/dashboard` | List all students |
| `/dev/students/<id>/edit` | Edit a student |
| `/dev/students/<id>/delete` | Delete a student |
| `/dev/countries` | Manage countries |
| `/dev/states` | Manage states |
| `/dev/cities` | Manage cities |
| `/dev/colleges` | Manage colleges / universities |
| `/dev/colleges/<id>/edit` | Edit a college |
| `/dev/courses` | Manage courses |
| `/dev/courses/<id>/edit` | Edit a course |

## REST API

All endpoints (except register and login) require an active session cookie.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/register` | Register a new student |
| POST | `/api/login` | Log in |
| POST | `/api/logout` | Log out |
| GET | `/api/profile` | Get current student's profile |
| GET | `/api/students` | List all students |
| GET | `/api/students/<id>` | Get a student by ID |
| PUT | `/api/students/<id>` | Update a student |
| DELETE | `/api/students/<id>` | Delete a student |
| GET | `/api/universities/by-country/<country_id>` | List universities for a country |

### Example: Register

```bash
curl -X POST http://127.0.0.1:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "email": "jane@example.com",
    "password": "secret123",
    "study_level": "Masters",
    "country": "Germany",
    "course": "Computer Science"
  }'
```

## Pre-seeded Universities

10 universities per country across these destinations:

| Country | Sample Universities |
|---|---|
| United States | MIT, Harvard, Stanford, Columbia, UC Berkeley, Yale, Princeton, UChicago, UPenn, Johns Hopkins |
| United Kingdom | Oxford, Cambridge, Imperial, UCL, LSE, Edinburgh, Manchester, King's College, Bristol, Warwick |
| Canada | University of Toronto, UBC, McGill, McMaster, University of Alberta, Waterloo, Western, Queen's, SFU, Dalhousie |
| Australia | Sydney, Melbourne, ANU, Queensland, Monash, UWA, Adelaide, UTS, RMIT, Macquarie |
| Switzerland | ETH Zurich, EPFL, University of Zurich, University of Geneva, Basel, Lausanne, Bern, St. Gallen, Lucerne, Fribourg |
| Germany | TU Munich, LMU Munich, Heidelberg, Free University Berlin, Humboldt Berlin, RWTH Aachen, KIT, Hamburg, Goethe Frankfurt, Cologne |
| Netherlands | TU Delft, University of Amsterdam, Leiden, Utrecht, Eindhoven TU, Groningen, VU Amsterdam, Wageningen, Maastricht, Tilburg |
| New Zealand | University of Auckland, Victoria Wellington, Otago, Canterbury, Massey, AUT, Waikato, Lincoln, EIT, Unitec |
| Ireland | Trinity College Dublin, UCD, UCC, University of Galway, DCU, Maynooth, UL, TU Dublin, MTU, SETU |
| Sweden | KTH, Lund, Uppsala, Stockholm University, Chalmers, Karolinska Institute, Gothenburg, Linköping, Umeå, Malmö |

## Production Deployment

Use Gunicorn (already in `requirements.txt`):

```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```
