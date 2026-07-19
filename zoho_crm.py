import requests
import json
import os

CLIENT_ID     = '1000.JR8LYQHM2SL6H0YP4ZD97DYCGSS7AX'
CLIENT_SECRET = 'd18564a0307da0215d2b75270e1b45b80846e51e35'
REDIRECT_URI  = 'http://127.0.0.1:5000/zoho/callback'
ACCOUNTS_URL  = 'https://accounts.zoho.com'
API_URL       = 'https://www.zohoapis.com'
TOKEN_FILE    = 'zoho_tokens.json'


def _save_tokens(data):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return {}


def exchange_code_for_tokens(code):
    resp = requests.post(f'{ACCOUNTS_URL}/oauth/v2/token', data={
        'code':          code,
        'client_id':     CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri':  REDIRECT_URI,
        'grant_type':    'authorization_code',
    })
    data = resp.json()
    _save_tokens(data)
    return data


def _get_access_token():
    tokens = _load_tokens()
    refresh_token = tokens.get('refresh_token')
    if not refresh_token:
        raise Exception('Zoho not authorized yet. Visit /zoho/auth first.')
    resp = requests.post(f'{ACCOUNTS_URL}/oauth/v2/token', data={
        'refresh_token': refresh_token,
        'client_id':     CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type':    'refresh_token',
    })
    return resp.json().get('access_token')


def create_lead(name, email, course, country, study_level, phone=None):
    access_token = _get_access_token()

    # Split name into first + last for Zoho's required Last_Name field
    parts = name.strip().split(' ', 1)
    first_name = parts[0] if len(parts) > 1 else ''
    last_name  = parts[-1]

    lead = {
        'First_Name':  first_name,
        'Last_Name':   last_name,
        'Email':       email,
        'Phone':       phone or '',
        'Lead_Source': 'Web Site',
        'Country':     country,
        'Description': f'Study Level: {study_level} | Course: {course} | Preferred Country: {country}',
    }

    resp = requests.post(
        f'{API_URL}/crm/v2/Leads',
        headers={
            'Authorization': f'Zoho-oauthtoken {access_token}',
            'Content-Type':  'application/json',
        },
        json={'data': [lead]}
    )
    return resp.json()
