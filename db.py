import psycopg2
import os
from psycopg2 import pool       # built-in psycopg2 pooling module
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()                   # reads credentials from .env file

# all DB credentials come from .env — never hardcoded here
DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),   # server address
    'database': os.environ.get('DB_NAME', 'student_portal'),  # database name
    'user':     os.environ.get('DB_USER', 'postgres'),    # DB username
    'password': os.environ.get('DB_PASSWORD'),            # DB password
    'port':     os.environ.get('DB_PORT', '5432'),        # PostgreSQL default port
}

# creates 2 connections at startup, allows up to 10 at the same time
connection_pool = pool.ThreadedConnectionPool(2, 10, **DB_CONFIG)

def get_connection():
    # borrows a free connection from the pool
    return connection_pool.getconn()

def release_connection(conn):
    # returns the connection back to the pool for reuse
    connection_pool.putconn(conn)

def create_table():
    conn = get_connection()
    cur = conn.cursor()
    # creates the students table only if it doesn't already exist
    cur.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            student_id INT,
            study_level VARCHAR(50),
            country VARCHAR(100),
            course VARCHAR(100),
            image_path VARCHAR(255),
            phone VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    # Add phone column to existing tables that predate this field
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS phone VARCHAR(20)")
        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()
    release_connection(conn)    # return connection back to pool


def create_admin_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id       SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    release_connection(conn)


def insert_default_admin():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM admins')
    count = cur.fetchone()[0]
    if count == 0:
        hashed = generate_password_hash('Dev@1234')
        cur.execute(
            'INSERT INTO admins (username, password) VALUES (%s, %s)',
            ('devadmin', hashed)
        )
        conn.commit()
    cur.close()
    release_connection(conn)


# ── College Directory Tables ───────────────────────────────────────────────────

def create_countries_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS countries (
            id         SERIAL PRIMARY KEY,
            name       VARCHAR(100) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    release_connection(conn)


def create_states_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS states (
            id         SERIAL PRIMARY KEY,
            name       VARCHAR(100) NOT NULL,
            country_id INT REFERENCES countries(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    release_connection(conn)


def create_cities_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cities (
            id         SERIAL PRIMARY KEY,
            name       VARCHAR(100) NOT NULL,
            state_id   INT REFERENCES states(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    release_connection(conn)


def create_colleges_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS colleges (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(200) NOT NULL,
            description TEXT,
            website     VARCHAR(200),
            city_id     INT REFERENCES cities(id),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    release_connection(conn)


def add_ranking_to_colleges():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute('ALTER TABLE colleges ADD COLUMN IF NOT EXISTS ranking INT')
    cur.execute('ALTER TABLE colleges ADD COLUMN IF NOT EXISTS tuition_fee_usd INT')
    cur.execute('ALTER TABLE colleges ADD COLUMN IF NOT EXISTS scholarship_info TEXT')
    conn.commit()
    cur.close()
    release_connection(conn)


# ── Seed data: 10 countries × 5 colleges each ────────────────────────────────
# Format: (country, state, city, name, description, website,
#           ranking, tuition_fee_usd, scholarship_info)
_SEED = [
    # ── United States ─────────────────────────────────────────────────────────
    ('United States','Massachusetts','Cambridge',
     'Massachusetts Institute of Technology',
     'World-leading STEM and engineering research university.',
     'www.mit.edu', 1, 57986,
     'Need-based aid only; meets 100% of demonstrated need. Average grant ~$57,000/yr.'),

    ('United States','Massachusetts','Cambridge',
     'Harvard University',
     'Ivy League; oldest university in the United States, founded 1636.',
     'www.harvard.edu', 4, 54269,
     'Need-blind for all applicants; average scholarship $55,000/yr. No-loan policy.'),

    ('United States','California','Stanford',
     'Stanford University',
     'Top-ranked private research university in Silicon Valley.',
     'www.stanford.edu', 3, 56169,
     'Knight-Hennessy Scholars: full funding + stipend. Need-based grants for families under $150k/yr income.'),

    ('United States','New York','New York City',
     'Columbia University',
     'Ivy League university in the heart of Manhattan.',
     'www.columbia.edu', 12, 65524,
     'Need-blind admissions; meets 100% of demonstrated need. International students eligible.'),

    ('United States','California','Berkeley',
     'University of California, Berkeley',
     'Premier public research university; world-class faculty and research output.',
     'www.berkeley.edu', 28, 44066,
     'Regents & Chancellor\'s Scholarship (merit). Blue & Gold Plan for families earning under $80k/yr.'),

    # ── United Kingdom ────────────────────────────────────────────────────────
    ('United Kingdom','England','Oxford',
     'University of Oxford',
     'World\'s oldest English-language university; global top 3.',
     'www.ox.ac.uk', 2, 36000,
     'Rhodes Scholarship: full funding for 100 scholars globally. Oxford-Weidenfeld & Hoffmann Scholarships for international students.'),

    ('United Kingdom','England','Cambridge',
     'University of Cambridge',
     'Leading research university; 121 Nobel Laureates affiliated.',
     'www.cam.ac.uk', 5, 32000,
     'Gates Cambridge Scholarship: full funding for 80 international students/yr.'),

    ('United Kingdom','England','London',
     'Imperial College London',
     'Specialist science, engineering and medicine university; top 10 globally.',
     'www.imperial.ac.uk', 6, 45000,
     'President\'s PhD Scholarships. Schrödinger Scholarship for outstanding STEM students.'),

    ('United Kingdom','England','London',
     'University College London',
     'Multidisciplinary research university in central London.',
     'www.ucl.ac.uk', 9, 33000,
     'UCL Global Undergraduate Scholarship. Denys Holland Scholarship for students with financial hardship.'),

    ('United Kingdom','England','London',
     'London School of Economics',
     'World-renowned for social sciences, economics, law, and politics.',
     'www.lse.ac.uk', 45, 28000,
     'LSE Scholarship for Excellence. Graduate Support Scheme for postgraduate students.'),

    # ── Canada ────────────────────────────────────────────────────────────────
    ('Canada','Ontario','Toronto',
     'University of Toronto',
     'Canada\'s leading research university; ranked in world top 25.',
     'www.utoronto.ca', 21, 34000,
     'Lester B. Pearson International Scholarship: full tuition + living costs. U of T Scholar Awards up to $7,500.'),

    ('Canada','British Columbia','Vancouver',
     'University of British Columbia',
     'Top research university on Canada\'s Pacific coast.',
     'www.ubc.ca', 34, 31000,
     'International Leader of Tomorrow Award: up to full tuition. Trek Excellence Scholarship for academic merit.'),

    ('Canada','Quebec','Montreal',
     'McGill University',
     'Canada\'s most international university; bilingual city campus.',
     'www.mcgill.ca', 46, 21000,
     'McGill Entrance Scholarships: up to $12,000/yr. Differential Fee Waivers for students from select countries.'),

    ('Canada','Ontario','Hamilton',
     'McMaster University',
     'Research-intensive university renowned for health sciences and engineering.',
     'www.mcmaster.ca', 152, 26000,
     'McMaster Excellence Scholarship: up to $12,000. International Entrance Bursary for financial need.'),

    ('Canada','Alberta','Edmonton',
     'University of Alberta',
     'One of Canada\'s top 5 research universities.',
     'www.ualberta.ca', 111, 23000,
     'International Student Scholarship: up to $9,000/yr. Provost\'s Doctoral Entrance Award for PhD students.'),

    # ── Australia ─────────────────────────────────────────────────────────────
    ('Australia','New South Wales','Sydney',
     'University of Sydney',
     'Australia\'s first university; global top 20 in multiple disciplines.',
     'www.sydney.edu.au', 19, 32000,
     'Sydney Scholars Awards: up to AUD 20,000. Vice-Chancellor\'s International Scholarships for top applicants.'),

    ('Australia','Victoria','Melbourne',
     'University of Melbourne',
     'Australia\'s top-ranked university; world-class research across all fields.',
     'www.unimelb.edu.au', 33, 30000,
     'Melbourne International Undergraduate Scholarship: 100% tuition. Graduate Research Scholarships available.'),

    ('Australia','Australian Capital Territory','Canberra',
     'Australian National University',
     'National research university; ranked in global top 30.',
     'www.anu.edu.au', 30, 30000,
     'ANU Chancellor\'s International Scholarship: 25–50% tuition. HDR Fee Remission Scholarships for research.'),

    ('Australia','Queensland','Brisbane',
     'University of Queensland',
     'Leading research university with a beautiful riverside campus.',
     'www.uq.edu.au', 40, 29000,
     'UQ Excellence Scholarships: up to AUD 10,000. UQ International Scholarships for high achievers.'),

    ('Australia','Victoria','Melbourne',
     'Monash University',
     'Largest Australian university by enrolment; campuses across 4 countries.',
     'www.monash.edu', 57, 28000,
     'Monash International Leadership Scholarship: 50% tuition waiver. Monash Graduate Scholarships for research.'),

    # ── Switzerland ───────────────────────────────────────────────────────────
    ('Switzerland','Zurich','Zurich',
     'ETH Zurich',
     'Europe\'s top technical university; Albert Einstein\'s alma mater.',
     'www.ethz.ch', 7, 800,
     'Excellence Scholarship & Opportunity Programme: full tuition + CHF 12,000 stipend/yr for Master\'s students.'),

    ('Switzerland','Vaud','Lausanne',
     'EPFL',
     'Top engineering school; innovation hub on the shores of Lake Geneva.',
     'www.epfl.ch', 14, 800,
     'Excellence Fellowships for Master\'s students. Doctoral School Fellowships (~CHF 50,000/yr stipend).'),

    ('Switzerland','Zurich','Zurich',
     'University of Zurich',
     'Switzerland\'s largest university; strong in medicine and life sciences.',
     'www.uzh.ch', 83, 800,
     'UZH Merit Scholarships for international students. Swiss Government Excellence Scholarships.'),

    ('Switzerland','Geneva','Geneva',
     'University of Geneva',
     'International campus near the UN headquarters and CERN.',
     'www.unige.ch', 114, 600,
     'Federal Excellence Scholarships for foreign nationals. IHEID Joint Scholarship Programme.'),

    ('Switzerland','Basel-City','Basel',
     'University of Basel',
     'Switzerland\'s oldest university, founded 1460; strong in pharma research.',
     'www.unibas.ch', 151, 950,
     'University of Basel Scholarships for international students. Swiss Government Excellence Scholarships.'),

    # ── Germany ───────────────────────────────────────────────────────────────
    ('Germany','Bavaria','Munich',
     'Technical University of Munich',
     'Germany\'s top technical university; close ties with BMW, Siemens, MAN.',
     'www.tum.de', 37, 200,
     'Deutschlandstipendium: €300/month for top students. DAAD Scholarships for international students.'),

    ('Germany','Bavaria','Munich',
     'Ludwig Maximilian University of Munich',
     'Elite research university; 42 Nobel Prize winners.',
     'www.lmu.de', 54, 200,
     'LMU Completion Grants. DAAD RISE Programme. Elitenetzwerk Bayern Excellence Scholarships.'),

    ('Germany','Baden-Württemberg','Heidelberg',
     'Heidelberg University',
     'Germany\'s oldest university, founded 1386; excellence in natural sciences.',
     'www.uni-heidelberg.de', 65, 200,
     'Heidelberg University Excellence Scholarship. Erasmus+ Scholarships for exchange programmes.'),

    ('Germany','Berlin','Berlin',
     'Free University of Berlin',
     'Major research university in the German capital; international campus.',
     'www.fu-berlin.de', 98, 200,
     'Dahlem Research School Fellowships. DAAD Scholarships. Heinrich Böll Foundation Grants.'),

    ('Germany','Berlin','Berlin',
     'Humboldt University of Berlin',
     'Alma mater of Marx, Einstein, and Hegel; excellence in humanities and sciences.',
     'www.hu-berlin.de', 117, 200,
     'HU Berlin International Scholarships. DAAD STIBET Scholarships. Fulbright Scholarships.'),

    # ── Netherlands ───────────────────────────────────────────────────────────
    ('Netherlands','South Holland','Delft',
     'Delft University of Technology',
     'Europe\'s top engineering university; renowned for aerospace and water management.',
     'www.tudelft.nl', 47, 18750,
     'Justus & Louise van Effen Excellence Scholarships: full tuition. Holland Scholarship: €5,000 for non-EEA students.'),

    ('Netherlands','North Holland','Amsterdam',
     'University of Amsterdam',
     'Top 55 globally; strong research across all academic disciplines.',
     'www.uva.nl', 53, 14900,
     'Amsterdam Excellence Scholarships: full tuition + €5,000 living costs. Holland Scholarship: €5,000.'),

    ('Netherlands','South Holland','Leiden',
     'Leiden University',
     'Netherlands\' oldest university; birthplace of Dutch academic tradition.',
     'www.universiteitleiden.nl', 60, 14900,
     'Leiden Excellence Scholarships: 50%–100% tuition waiver. Holland Scholarship: €5,000.'),

    ('Netherlands','Utrecht','Utrecht',
     'Utrecht University',
     'Comprehensive research university; Utrecht is Europe\'s student city.',
     'www.uu.nl', 64, 15000,
     'Utrecht Excellence Scholarships: full tuition + €11,000/yr living allowance. Holland Scholarship: €5,000.'),

    ('Netherlands','North Brabant','Eindhoven',
     'Eindhoven University of Technology',
     'Innovation-focused tech university in the Brainport high-tech region.',
     'www.tue.nl', 147, 17500,
     'TU/e Excellence Scholarships for outstanding international students. Holland Scholarship: €5,000.'),

    # ── New Zealand ───────────────────────────────────────────────────────────
    ('New Zealand','Auckland Region','Auckland',
     'University of Auckland',
     'New Zealand\'s highest-ranked university; global top 70.',
     'www.auckland.ac.nz', 68, 22000,
     'International Student Excellence Scholarship: up to NZD 10,000/yr. Doctoral Scholarships for research.'),

    ('New Zealand','Wellington Region','Wellington',
     'Victoria University of Wellington',
     'New Zealand\'s capital-city university; strong in law, politics and design.',
     'www.wgtn.ac.nz', 221, 20000,
     'VUW Vice-Chancellor\'s Scholarship. Wellington Faculty Scholarships up to NZD 10,000.'),

    ('New Zealand','Otago Region','Dunedin',
     'University of Otago',
     'New Zealand\'s oldest university; ranked highly in health sciences.',
     'www.otago.ac.nz', 206, 18000,
     'Otago International Excellence Scholarship: up to NZD 10,000. Coursework Masters Scholarship.'),

    ('New Zealand','Canterbury Region','Christchurch',
     'University of Canterbury',
     'Engineering and science-focused; rebuilt as a world-class campus after 2011.',
     'www.canterbury.ac.nz', 255, 19000,
     'UC International Excellence Award: up to NZD 10,000. Doctoral Scholarship for research degrees.'),

    ('New Zealand','Manawatu-Whanganui','Palmerston North',
     'Massey University',
     'Multi-campus university known for agriculture, aviation, and creative arts.',
     'www.massey.ac.nz', 351, 17000,
     'Massey University Scholarships: up to NZD 5,000/yr. Vice-Chancellor\'s Doctoral Scholarship.'),

    # ── Ireland ───────────────────────────────────────────────────────────────
    ('Ireland','Leinster','Dublin',
     'Trinity College Dublin',
     'Ireland\'s top university, founded 1592; home of the Book of Kells.',
     'www.tcd.ie', 81, 25000,
     'Trinity Global Excellence Scholarship: up to €5,000. Provost\'s PhD Project Awards for research.'),

    ('Ireland','Leinster','Dublin',
     'University College Dublin',
     'Ireland\'s largest university; strong in business, agriculture, and law.',
     'www.ucd.ie', 138, 20000,
     'UCD Global Excellence Scholarship: up to €3,000. Government of Ireland International Education Scholarships.'),

    ('Ireland','Munster','Cork',
     'University College Cork',
     'Research university in Ireland\'s pharmaceutical and food capital.',
     'www.ucc.ie', 303, 18000,
     'UCC International Student Scholarship: 10–25% tuition reduction. Government of Ireland Scholarships.'),

    ('Ireland','Connacht','Galway',
     'University of Galway',
     'Research university on the Atlantic coast; vibrant arts and culture scene.',
     'www.universityofgalway.ie', 259, 17500,
     'University of Galway International Scholarships. Government of Ireland International Education Scholarships.'),

    ('Ireland','Leinster','Dublin',
     'Dublin City University',
     'Modern career-focused university; strong in technology, media, and nursing.',
     'www.dcu.ie', 451, 16000,
     'DCU Excellence Scholarship: up to €3,000. Loop Scholarships for postgraduate students.'),

    # ── Sweden ────────────────────────────────────────────────────────────────
    ('Sweden','Stockholm County','Stockholm',
     'KTH Royal Institute of Technology',
     'Sweden\'s leading technical university; ranked global top 100.',
     'www.kth.se', 92, 18000,
     'KTH Scholarship: 100% tuition waiver for top-ranked non-EU applicants.'),

    ('Sweden','Scania','Lund',
     'Lund University',
     'Scandinavia\'s largest university; strong research and innovation culture.',
     'www.lu.se', 97, 17500,
     'Lund University Global Scholarship: full tuition for non-EU students. SISS Scholarship.'),

    ('Sweden','Uppsala County','Uppsala',
     'Uppsala University',
     'Oldest university in Scandinavia, founded 1477; excellence in sciences.',
     'www.uu.se', 107, 16000,
     'Uppsala University Global Scholarship. Sweden\'s Institute Scholarships for Global Professionals.'),

    ('Sweden','Stockholm County','Stockholm',
     'Stockholm University',
     'Comprehensive research university in Europe\'s innovation capital.',
     'www.su.se', 165, 15000,
     'Stockholm University Scholarships: full tuition waivers for top non-EU students.'),

    ('Sweden','Västra Götaland','Gothenburg',
     'Chalmers University of Technology',
     'Engineering and technology university; partners include Volvo and Ericsson.',
     'www.chalmers.se', 166, 18000,
     'Chalmers IPOET Scholarship: full tuition + SEK 10,000/month stipend. SI Scholarships.'),

    # ── United States (5 more) ────────────────────────────────────────────────
    ('United States','Connecticut','New Haven',
     'Yale University',
     'Ivy League university founded 1701; world-renowned for law, medicine, and the arts.',
     'www.yale.edu', 8, 62250,
     'Need-blind for all applicants; meets 100% of demonstrated need. Average grant ~$60,000/yr.'),

    ('United States','New Jersey','Princeton',
     'Princeton University',
     'Ivy League university; ranked #1 for undergraduate teaching in the US.',
     'www.princeton.edu', 6, 57990,
     'No-loan financial aid policy; all aid given as grants. Meets 100% of demonstrated need.'),

    ('United States','Illinois','Chicago',
     'University of Chicago',
     'World-renowned research university; birthplace of the Chicago School of Economics.',
     'www.uchicago.edu', 10, 62166,
     'No-loan policy; all financial aid in grants. Merit Scholarships up to full tuition available.'),

    ('United States','Pennsylvania','Philadelphia',
     'University of Pennsylvania',
     'Ivy League university; home to the world-famous Wharton School of Business.',
     'www.upenn.edu', 13, 63452,
     'Penn Grant replaces all loans with grants. Need-blind admissions for domestic students.'),

    ('United States','Maryland','Baltimore',
     'Johns Hopkins University',
     'Global leader in medicine, public health, and biomedical research.',
     'www.jhu.edu', 25, 60480,
     'Hopkins Meets Need: 100% of demonstrated need met. Bloomberg Legacy Scholarships for first-generation students.'),

    # ── United Kingdom (5 more) ───────────────────────────────────────────────
    ('United Kingdom','Scotland','Edinburgh',
     'University of Edinburgh',
     'Ancient university founded 1583; global leader in medicine, law, and informatics.',
     'www.ed.ac.uk', 22, 34000,
     'Edinburgh Global Scholarships: up to £10,000. Saltire Scholarships for students from select countries.'),

    ('United Kingdom','England','Manchester',
     'University of Manchester',
     'Red-brick research university; 25 Nobel Prize winners among alumni and staff.',
     'www.manchester.ac.uk', 32, 33000,
     'Manchester Global Futures Scholarships: £5,000–£10,000. President\'s Doctoral Scholarship Award.'),

    ('United Kingdom','England','London',
     "King's College London",
     "One of England's oldest universities; top-ranked for law, nursing, and dentistry.",
     'www.kcl.ac.uk', 40, 35000,
     "King's College London Merit Scholarships for international students up to £5,000/yr."),

    ('United Kingdom','England','Bristol',
     'University of Bristol',
     'Russell Group university in a vibrant city; top-ranked for engineering and science.',
     'www.bristol.ac.uk', 54, 30000,
     'Think Big Postgraduate Scholarships: up to £20,000. Bristol Global Scholarship for undergraduates.'),

    ('United Kingdom','England','Coventry',
     'University of Warwick',
     'Highly ranked for business, economics, and computer science; campus near Birmingham.',
     'www.warwick.ac.uk', 67, 31000,
     'Warwick International Excellence Scholarships. Chancellor\'s International Scholarships for postgraduates.'),

    # ── Canada (5 more) ───────────────────────────────────────────────────────
    ('Canada','Ontario','Waterloo',
     'University of Waterloo',
     'World-leading engineering and computer science university; largest co-op programme globally.',
     'www.uwaterloo.ca', 112, 28000,
     'President\'s Scholarship of Distinction: up to $2,000/yr. International Master\'s and Doctoral Awards.'),

    ('Canada','Ontario','London',
     'Western University',
     'Comprehensive research university; highly ranked for business and medical sciences.',
     'www.uwo.ca', 172, 24000,
     'Western Scholarship of Excellence: up to $3,000. International Student Entrance Scholarship available.'),

    ('Canada','Ontario','Kingston',
     "Queen's University",
     'Historic research university; renowned for business, engineering, and medicine.',
     'www.queensu.ca', 246, 29000,
     "Queen's University International Scholarships: up to $10,000/yr. Chancellor's Scholarships."),

    ('Canada','British Columbia','Burnaby',
     'Simon Fraser University',
     'Innovative Canadian university across 3 Metro Vancouver campuses.',
     'www.sfu.ca', 298, 21000,
     'SFU International Renewable Entrance Scholarships: up to $12,000. Graduate Fellowships.'),

    ('Canada','Nova Scotia','Halifax',
     'Dalhousie University',
     "Canada's leading ocean and marine research university; strong in medicine and law.",
     'www.dal.ca', 302, 19000,
     'Dalhousie Excellence Scholarship: up to $12,000. International Student Scholarship: up to $6,000.'),

    # ── Australia (5 more) ────────────────────────────────────────────────────
    ('Australia','Western Australia','Perth',
     'University of Western Australia',
     'Research-intensive Group of Eight university; beautiful riverside campus in Perth.',
     'www.uwa.edu.au', 72, 27000,
     'UWA Global Excellence Scholarship: 25% tuition reduction. International Research Scholarships.'),

    ('Australia','South Australia','Adelaide',
     'University of Adelaide',
     "Member of Australia's Group of Eight; strong in engineering, wine, and agriculture.",
     'www.adelaide.edu.au', 89, 25000,
     'Adelaide Scholarship International: full tuition + living allowance. Merit Scholarships available.'),

    ('Australia','New South Wales','Sydney',
     'University of Technology Sydney',
     'Career-focused university; top-ranked for graduate employability in Australia.',
     'www.uts.edu.au', 133, 25000,
     'UTS International Scholarship: 25%–50% tuition waiver. UTS Postgraduate Research Scholarships.'),

    ('Australia','Victoria','Melbourne',
     'RMIT University',
     'Practice-based university; strong links with industry and creative sectors globally.',
     'www.rmit.edu.au', 140, 25000,
     'RMIT STEM Scholarship: up to AUD 10,000. RMIT International Excellence Scholarship.'),

    ('Australia','New South Wales','Sydney',
     'Macquarie University',
     "Research university known for innovation; home to Australia's first university hospital.",
     'www.mq.edu.au', 195, 26000,
     'Macquarie International Scholarship: 20% tuition waiver. Vice-Chancellor\'s Innovation Scholarship.'),

    # ── Switzerland (5 more) ─────────────────────────────────────────────────
    ('Switzerland','Vaud','Lausanne',
     'University of Lausanne',
     'Comprehensive research university on the shores of Lake Geneva; strong in business.',
     'www.unil.ch', 171, 600,
     'Swiss Government Excellence Scholarships. University of Lausanne Merit Scholarships for international students.'),

    ('Switzerland','Bern','Bern',
     'University of Bern',
     'Comprehensive research university; world-leading in climate, space, and medical sciences.',
     'www.unibe.ch', 130, 900,
     'Swiss Government Excellence Scholarships. University of Bern International Scholarships.'),

    ('Switzerland','St. Gallen','St. Gallen',
     'University of St. Gallen',
     "Europe's top-ranked business school; located in eastern Switzerland.",
     'www.unisg.ch', 178, 1200,
     'HSG Scholarships for outstanding international students. Swiss Government Excellence Scholarships.'),

    ('Switzerland','Lucerne','Lucerne',
     'University of Lucerne',
     'Boutique university in scenic central Switzerland; strong in humanities and law.',
     'www.unilu.ch', 501, 800,
     'Swiss Government Excellence Scholarships. University of Lucerne Exchange Scholarships.'),

    ('Switzerland','Fribourg','Fribourg',
     'University of Fribourg',
     'Bilingual university (French & German) near the Alps; strong in theology and sciences.',
     'www.unifr.ch', 501, 700,
     'Swiss Government Excellence Scholarships. University of Fribourg International Scholarships.'),

    # ── Germany (5 more) ──────────────────────────────────────────────────────
    ('Germany','North Rhine-Westphalia','Aachen',
     'RWTH Aachen University',
     "Germany's largest technical university; world leader in engineering and natural sciences.",
     'www.rwth-aachen.de', 106, 200,
     'Deutschlandstipendium: €300/month. DAAD Scholarships. Excellence Initiative Fellowships.'),

    ('Germany','Baden-Württemberg','Karlsruhe',
     'Karlsruhe Institute of Technology',
     'Elite research university; strong partnerships with SAP, Bosch, and Siemens.',
     'www.kit.edu', 119, 200,
     'KIT Excellence Scholarship. Deutschlandstipendium: €300/month. DAAD Scholarships.'),

    ('Germany','Hamburg','Hamburg',
     'University of Hamburg',
     "One of Germany's largest universities; strong in climate research, law, and physics.",
     'www.uni-hamburg.de', 170, 200,
     'Deutschlandstipendium: €300/month. DAAD Scholarships. Hamburg State Scholarships.'),

    ('Germany','Hesse','Frankfurt',
     'Goethe University Frankfurt',
     'Major research university in Germany\'s financial capital; strong in finance and law.',
     'www.uni-frankfurt.de', 201, 200,
     'Goethe University Scholarships. Deutschlandstipendium: €300/month. DAAD Scholarships.'),

    ('Germany','North Rhine-Westphalia','Cologne',
     'University of Cologne',
     "One of Germany's oldest and largest universities; strong in business and medicine.",
     'www.uni-koeln.de', 218, 200,
     'Cologne Scholarships for International Students. Deutschlandstipendium: €300/month.'),

    # ── Netherlands (5 more) ─────────────────────────────────────────────────
    ('Netherlands','Groningen','Groningen',
     'University of Groningen',
     '12 Nobel Prize winners; one of the oldest universities in the Netherlands.',
     'www.rug.nl', 128, 14500,
     'University of Groningen Scholarship: up to full tuition. Holland Scholarship: €5,000.'),

    ('Netherlands','North Holland','Amsterdam',
     'Vrije Universiteit Amsterdam',
     'Liberal university; strong in social sciences, health, and sustainability.',
     'www.vu.nl', 170, 15500,
     'VU Amsterdam Fellowship Programme for non-EEA students. Holland Scholarship: €5,000.'),

    ('Netherlands','Gelderland','Wageningen',
     'Wageningen University & Research',
     "World's #1 university for agriculture, food, and environmental sciences.",
     'www.wur.nl', 166, 16500,
     'Wageningen Excellence Scholarship: full tuition + living costs. Holland Scholarship: €5,000.'),

    ('Netherlands','Limburg','Maastricht',
     'Maastricht University',
     'Problem-based learning pioneer; 50%+ international students from 100+ countries.',
     'www.maastrichtuniversity.nl', 276, 14500,
     'Maastricht University High Potential Scholarship: full tuition. Holland Scholarship: €5,000.'),

    ('Netherlands','North Brabant','Tilburg',
     'Tilburg University',
     'Specialist in social sciences, law, economics, and data science.',
     'www.tilburguniversity.edu', 401, 14000,
     'Tilburg University Scholarships for Excellence. Holland Scholarship: €5,000.'),

    # ── New Zealand (5 more) ─────────────────────────────────────────────────
    ('New Zealand','Auckland Region','Auckland',
     'Auckland University of Technology',
     "New Zealand's fastest-growing university; strong in health, creative industries, and tech.",
     'www.aut.ac.nz', 401, 21000,
     'AUT International Student Scholarship: up to NZD 5,000. Vice-Chancellor\'s Excellence Scholarship.'),

    ('New Zealand','Waikato Region','Hamilton',
     'University of Waikato',
     'Research-led university known for law, management, computing, and Maori studies.',
     'www.waikato.ac.nz', 501, 19000,
     'Waikato International Excellence Scholarship: up to NZD 10,000. Doctoral Scholarship.'),

    ('New Zealand','Canterbury Region','Lincoln',
     'Lincoln University',
     'Specialist in land-based industries, agriculture, environment, and commerce.',
     'www.lincoln.ac.nz', 551, 17000,
     'Lincoln University International Scholarship: up to NZD 10,000. Research Scholarships.'),

    ('New Zealand','Hawkes Bay Region','Napier',
     'Eastern Institute of Technology',
     'Regional university with growing programmes in IT, nursing, and creative arts.',
     'www.eit.ac.nz', 601, 15000,
     'EIT International Scholarships. New Zealand Government Scholarships for select countries.'),

    ('New Zealand','Auckland Region','Henderson',
     'Unitec Institute of Technology',
     'Practice-based institute offering degrees in engineering, construction, and business.',
     'www.unitec.ac.nz', 651, 14000,
     'Unitec International Scholarships. New Zealand Government Scholarships.'),

    # ── Ireland (5 more) ─────────────────────────────────────────────────────
    ('Ireland','Leinster','Maynooth',
     'Maynooth University',
     'Modern campus university; strong in humanities, science, and social sciences.',
     'www.maynoothuniversity.ie', 451, 14000,
     'Maynooth International Scholarship: up to €2,500. Government of Ireland Scholarships.'),

    ('Ireland','Munster','Limerick',
     'University of Limerick',
     "Innovative university; Ireland's leading institution for cooperative education and STEM.",
     'www.ul.ie', 501, 15000,
     'UL International Excellence Scholarship: up to €3,000. Government of Ireland Scholarships.'),

    ('Ireland','Leinster','Dublin',
     'Technological University Dublin',
     "Ireland's largest higher education institution; strong in technology and business.",
     'www.tudublin.ie', 551, 13500,
     'TU Dublin International Scholarships. Government of Ireland International Education Scholarships.'),

    ('Ireland','Munster','Cork',
     'Munster Technological University',
     'Applied and technological university; strong in engineering, science, and business.',
     'www.mtu.ie', 601, 13000,
     'MTU International Scholarships. Government of Ireland International Education Scholarships.'),

    ('Ireland','Munster','Waterford',
     'South East Technological University',
     "Regional university serving Ireland's south-east; strong in engineering and computing.",
     'www.setu.ie', 651, 12500,
     'SETU International Scholarships. Government of Ireland International Education Scholarships.'),

    # ── Sweden (5 more) ───────────────────────────────────────────────────────
    ('Sweden','Stockholm County','Stockholm',
     'Karolinska Institute',
     'World-premier medical university; awards the Nobel Prize in Physiology or Medicine.',
     'www.ki.se', 38, 16000,
     'Karolinska Institute International Scholarships. SI Scholarships for Global Professionals.'),

    ('Sweden','Västra Götaland','Gothenburg',
     'University of Gothenburg',
     'Comprehensive research university; strong in natural sciences, arts, and social sciences.',
     'www.gu.se', 175, 14000,
     'University of Gothenburg Scholarships for non-EU students. SI Scholarships for Global Professionals.'),

    ('Sweden','Östergötland','Linköping',
     'Linköping University',
     'Research university known for IT, engineering, and medicine; innovative campus design.',
     'www.liu.se', 401, 14500,
     'LiU International Scholarships for outstanding students. Sweden Institute Scholarships.'),

    ('Sweden','Västernorrland','Umeå',
     'Umeå University',
     'Innovative northern university; world-renowned for CRISPR gene-editing research.',
     'www.umu.se', 451, 13500,
     'Umeå University Scholarships for non-EU/EEA students. SI Scholarships for Global Professionals.'),

    ('Sweden','Scania','Malmö',
     'Malmö University',
     'Urban university focused on sustainability, equality, and applied research.',
     'www.mau.se', 601, 12000,
     'Malmö University International Scholarships. SI Scholarships for Global Professionals.'),
]


def seed_data():
    """Insert the 10 countries + states + cities + 100 colleges (10 per country).
    Safe to run on every startup — skips rows that already exist."""
    conn = get_connection()
    cur  = conn.cursor()

    for (country, state, city, name, desc, website,
         ranking, tuition_usd, scholarship) in _SEED:

        # 1. Country
        cur.execute('INSERT INTO countries (name) VALUES (%s) ON CONFLICT (name) DO NOTHING', (country,))
        cur.execute('SELECT id FROM countries WHERE name = %s', (country,))
        country_id = cur.fetchone()[0]

        # 2. State — no unique constraint exists, so check manually
        cur.execute('SELECT id FROM states WHERE name = %s AND country_id = %s', (state, country_id))
        row = cur.fetchone()
        if row:
            state_id = row[0]
        else:
            cur.execute('INSERT INTO states (name, country_id) VALUES (%s, %s) RETURNING id', (state, country_id))
            state_id = cur.fetchone()[0]

        # 3. City
        cur.execute('SELECT id FROM cities WHERE name = %s AND state_id = %s', (city, state_id))
        row = cur.fetchone()
        if row:
            city_id = row[0]
        else:
            cur.execute('INSERT INTO cities (name, state_id) VALUES (%s, %s) RETURNING id', (city, state_id))
            city_id = cur.fetchone()[0]

        # 4. College — skip if name already exists in this city
        cur.execute('SELECT id FROM colleges WHERE name = %s AND city_id = %s', (name, city_id))
        if not cur.fetchone():
            cur.execute('''
                INSERT INTO colleges
                    (name, description, website, city_id, ranking, tuition_fee_usd, scholarship_info)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (name, desc, website, city_id, ranking, tuition_usd, scholarship))

    conn.commit()
    cur.close()
    release_connection(conn)


def create_courses_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id           SERIAL PRIMARY KEY,
            name         VARCHAR(200) NOT NULL,
            level        VARCHAR(50),
            fee_per_year INT,
            currency     VARCHAR(10),
            duration     VARCHAR(50),
            description  TEXT,
            college_id   INT REFERENCES colleges(id),
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    release_connection(conn)


def seed_courses():
    """Insert representative courses (one per level) for every college that has none.
    Safe to run on every startup — skips colleges that already have courses seeded."""
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute('SELECT id, name FROM colleges ORDER BY id')
    colleges = cur.fetchall()

    # Institutions that only run postgraduate programmes (no Bachelors)
    postgrad_only = {
        'Karolinska Institute',
        'London School of Economics',
    }
    # Primarily teaching / vocational — limited or no doctoral research stream
    no_phd_set = {
        'Eastern Institute of Technology',
        'Unitec Institute of Technology',
        'Malmö University',
        'Technological University Dublin',
        'Munster Technological University',
        'South East Technological University',
        'Dublin City University',
    }

    # Representative courses per level
    _LEVEL_COURSES = {
        'Bachelors': [
            ('BSc Computer Science', '3 years',
             'Undergraduate programme covering algorithms, software engineering, and systems design.'),
            ('BA Business Administration', '3 years',
             'Undergraduate business degree with modules in finance, marketing, and management.'),
            ('BEng Engineering', '4 years',
             'Accredited undergraduate engineering degree with specialisations in mechanical, civil, or electrical.'),
        ],
        'Masters': [
            ('MSc Data Science & Artificial Intelligence', '1 year',
             'Advanced postgraduate programme in machine learning, big data analytics, and AI applications.'),
            ('MBA Business Administration', '2 years',
             'Globally recognised MBA developing leadership, strategy, and cross-functional business skills.'),
            ('MSc Computer Science', '1 year',
             'Postgraduate programme in advanced algorithms, distributed computing, and software research.'),
        ],
        'PhD': [
            ('PhD Computer Science & Engineering', '4 years',
             'Doctoral research programme producing original contributions to computing and engineering.'),
            ('PhD Natural Sciences', '3 years',
             'Research doctorate in physics, chemistry, biology, or environmental science.'),
            ('PhD Business & Economics', '4 years',
             'Doctoral programme conducting original research in finance, economics, or management.'),
        ],
        'Diploma': [
            ('Postgraduate Diploma in Business Management', '1 year',
             'Intensive postgraduate diploma covering core business management principles and practice.'),
            ('Diploma in Information Technology', '1 year',
             'Practical qualification in software development, networking, and IT project management.'),
        ],
    }

    for college_id, college_name in colleges:
        cur.execute('SELECT COUNT(*) FROM courses WHERE college_id = %s', (college_id,))
        if cur.fetchone()[0] > 0:
            continue  # already seeded for this college

        levels_to_add = ['Masters', 'Diploma']
        if college_name not in postgrad_only:
            levels_to_add = ['Bachelors'] + levels_to_add
        if college_name not in no_phd_set:
            levels_to_add.append('PhD')

        for level in levels_to_add:
            for (cname, duration, desc) in _LEVEL_COURSES[level]:
                cur.execute('''
                    INSERT INTO courses
                        (name, level, fee_per_year, currency, duration, description, college_id)
                    VALUES (%s, %s, NULL, 'USD', %s, %s, %s)
                ''', (cname, level, duration, desc, college_id))

    conn.commit()
    cur.close()
    release_connection(conn)


def seed_expanded_courses():
    """Add specific discipline-named courses (CS, PM, AI, MBA, etc.) to all colleges.
    Idempotent — skips any course name that already exists for that college."""
    conn = get_connection()
    cur  = conn.cursor()

    _EXPANDED = [
        # ── Bachelors ─────────────────────────────────────────────────────────
        ('BSc Software Engineering',               'Bachelors', '4 years',
         'Software design, development lifecycle, testing, and agile delivery.'),
        ('BSc Data Science & Analytics',           'Bachelors', '3 years',
         'Statistics, machine learning, Python/R, SQL, and data visualisation.'),
        ('BSc Artificial Intelligence',            'Bachelors', '3-4 years',
         'Neural networks, computer vision, NLP, robotics, and AI ethics.'),
        ('BSc Cybersecurity',                      'Bachelors', '3 years',
         'Network security, cryptography, ethical hacking, and digital forensics.'),
        ('BSc Electrical & Electronic Engineering','Bachelors', '4 years',
         'Circuits, embedded systems, power electronics, and signal processing.'),
        ('BSc Mechanical Engineering',             'Bachelors', '4 years',
         'Thermodynamics, fluid dynamics, CAD, manufacturing, and robotics.'),
        ('BA Economics',                           'Bachelors', '3 years',
         'Macro/microeconomics, econometrics, international trade, and policy.'),
        ('BA International Business',              'Bachelors', '3-4 years',
         'Global business strategy, cross-cultural management, and trade law.'),
        ('BSc Finance & Accounting',               'Bachelors', '3 years',
         'Financial reporting, investment analysis, taxation, and auditing.'),
        ('BSc Information Systems',                'Bachelors', '3 years',
         'Enterprise systems, database design, ERP, and digital transformation.'),
        # ── Masters ───────────────────────────────────────────────────────────
        ('MSc Cybersecurity & Network Security',   'Masters', '1 year',
         'Threat analysis, penetration testing, cloud security, and compliance.'),
        ('MSc Software Engineering',               'Masters', '1-2 years',
         'Advanced software architecture, DevOps, microservices, and cloud-native.'),
        ('MSc Project Management',                 'Masters', '1 year',
         'Agile, PRINCE2, PMP frameworks, stakeholder management, and risk.'),
        ('MSc Information Systems Management',     'Masters', '1 year',
         'IT governance, enterprise architecture, and digital business strategy.'),
        ('MSc Finance & Investment',               'Masters', '1 year',
         'Portfolio management, derivatives, financial modelling, and risk analysis.'),
        ('MSc International Business',             'Masters', '1 year',
         'Global markets, cross-border operations, and emerging-economy strategy.'),
        ('MSc Supply Chain & Operations',          'Masters', '1 year',
         'Logistics, procurement, lean operations, and sustainability management.'),
        ('MBA International Management',           'Masters', '2 years',
         'Global strategy, cross-cultural leadership, and entrepreneurship.'),
        # ── PhD ───────────────────────────────────────────────────────────────
        ('PhD Data Science & Machine Learning',    'PhD', '3-4 years',
         'Doctoral research in statistical learning, deep learning, or data systems.'),
        ('PhD Electrical Engineering',             'PhD', '3-4 years',
         'Research in power systems, VLSI, photonics, or signal processing.'),
        ('PhD Mechanical Engineering',             'PhD', '3-5 years',
         'Research in robotics, manufacturing, fluid dynamics, or materials.'),
        ('PhD Economics & Econometrics',           'PhD', '3-5 years',
         'Applied econometrics, economic theory, or development economics.'),
        ('PhD Biomedical Sciences',                'PhD', '3-4 years',
         'Medical research, drug discovery, genomics, or neuroscience.'),
        # ── Diploma ───────────────────────────────────────────────────────────
        ('Diploma in Data Analytics',              'Diploma', '6-12 months',
         'Excel, SQL, Python, Tableau — practical business analytics skills.'),
        ('Diploma in Project Management',          'Diploma', '6-12 months',
         'Agile, Scrum, PRINCE2, and PMP examination preparation.'),
        ('Diploma in Digital Marketing',           'Diploma', '6-12 months',
         'SEO, SEM, social media strategy, content marketing, and analytics.'),
    ]

    cur.execute('SELECT id FROM colleges ORDER BY id')
    college_ids = [r[0] for r in cur.fetchall()]

    for college_id in college_ids:
        for (name, level, duration, desc) in _EXPANDED:
            cur.execute(
                'SELECT 1 FROM courses WHERE college_id = %s AND name = %s',
                (college_id, name)
            )
            if not cur.fetchone():
                cur.execute('''
                    INSERT INTO courses
                        (name, level, fee_per_year, currency, duration, description, college_id)
                    VALUES (%s, %s, NULL, 'USD', %s, %s, %s)
                ''', (name, level, duration, desc, college_id))

    conn.commit()
    cur.close()
    release_connection(conn)
