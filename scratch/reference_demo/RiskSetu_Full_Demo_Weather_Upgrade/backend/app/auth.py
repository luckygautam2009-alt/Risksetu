import hashlib
import hmac
import os
import secrets
import time
import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app import config
from app.store import repo

bearer = HTTPBearer(auto_error=False)
sessions = {}

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()

def public_profile(profile):
    return {k:v for k,v in profile.items() if k not in {'password_hash','salt'}}

def create_user(email, password, name, role='citizen', verified=False):
    salt = secrets.token_hex(16)
    return repo.insert('profiles', {'email': email.lower(), 'full_name': name, 'role': role,
        'officer_verified': verified, 'officer_requested': False, 'preferred_language':'en',
        'salt':salt, 'password_hash':password_hash(password, salt)})

def demo_seed():
    if config.DATA_MODE != 'mock':
        return
    existing = {p['email'] for p in repo.all('profiles')}
    for email, name, role in [('citizen@risksetu.demo','Aarav Das','citizen'),('officer@risksetu.demo','Ananya Bora','officer'),('admin@risksetu.demo','Demo Administrator','admin')]:
        if email not in existing:
            create_user(email, os.getenv('DEMO_PASSWORD','RiskSetuDemo!2026'), name, role, role != 'citizen')

def issue_session(profile):
    token = secrets.token_urlsafe(40)
    sessions[token] = (profile['id'], time.time()+12*3600)
    return {'access_token': token, 'profile': public_profile(profile), 'expires_in':43200}

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, 'Please sign in')
    token = credentials.credentials
    if config.DATA_MODE == 'mock':
        session = sessions.get(token)
        if not session or session[1] < time.time():
            sessions.pop(token, None)
            raise HTTPException(401, 'Session expired; sign in again')
        profile = repo.get('profiles', session[0])
    else:
        with httpx.Client(timeout=15) as client:
            response = client.get(f'{config.SUPABASE_URL}/auth/v1/user', headers={
                'apikey': config.SUPABASE_ANON_KEY, 'Authorization': f'Bearer {token}'})
        if response.status_code != 200:
            raise HTTPException(401, 'Invalid session')
        profile = repo.get('profiles', response.json()['id'])
    if not profile:
        raise HTTPException(401, 'Profile not found')
    return public_profile(profile)

def officer(user=Depends(current_user)):
    if user['role'] not in {'officer','admin'} or not user.get('officer_verified'):
        raise HTTPException(403, 'Approved officer access required')
    return user

def admin(user=Depends(officer)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Administrator access required')
    return user
