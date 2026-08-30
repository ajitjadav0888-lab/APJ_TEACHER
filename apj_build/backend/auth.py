import base64, hashlib, hmac, json, os, secrets, time
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import Session
from app import Base, User, db

AUTH_SECRET = os.getenv('APJ_AUTH_SECRET') or os.getenv('SESSION_SECRET')
APP_ENV = os.getenv('APJ_ENV', 'development').lower()
if not AUTH_SECRET or len(AUTH_SECRET) < 32:
    if APP_ENV == 'production':
        raise RuntimeError('APJ_AUTH_SECRET must be set to a random secret of at least 32 characters in production')
    AUTH_SECRET = 'dev-only-apj-secret-change-before-production-32chars'
TOKEN_TTL = int(os.getenv('APJ_TOKEN_TTL', '3600'))
REFRESH_TTL = int(os.getenv('APJ_REFRESH_TTL', '2592000'))

class AuthCredential(Base):
    __tablename__ = 'auth_credentials'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    password_hash = Column(String, nullable=False)

class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    school_id = Column(Integer, nullable=False)
    refresh_hash = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    refresh_rotated_at = Column(DateTime, nullable=True)

class LoginIn(BaseModel):
    user_id: int = Field(gt=0)
    password: str = Field(min_length=8)

class CredentialIn(BaseModel):
    user_id: int = Field(gt=0)
    password: str = Field(min_length=8)

class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=32)

class _LogoutIn(BaseModel):
    pass

def _hash_password(password: str, salt: bytes | None = None):
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210_000)
    return base64.urlsafe_b64encode(salt).decode() + ':' + base64.urlsafe_b64encode(dk).decode()

def _verify_password(password, stored):
    try:
        s, d = stored.split(':', 1)
        salt = base64.urlsafe_b64decode(s.encode())
        expected = base64.urlsafe_b64decode(d.encode())
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def _sign(payload):
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
    sig = hmac.new(AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw + '.' + sig

def _decode(token):
    try:
        raw, sig = token.split('.', 1)
        expected = hmac.new(AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected): raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)))
        if payload['exp'] < int(time.time()): raise ValueError
        return payload
    except Exception:
        raise HTTPException(401, 'Invalid or expired token')

def _hash_refresh(token: str) -> str:
    return hmac.new(AUTH_SECRET.encode(), token.encode(), hashlib.sha256).hexdigest()

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _issue_session(user, session: Session):
    now = int(time.time())
    sid = secrets.token_urlsafe(24)
    refresh = secrets.token_urlsafe(48)
    db_session = AuthSession(id=sid, user_id=user.id, school_id=user.school_id, refresh_hash=_hash_refresh(refresh), created_at=_now(), expires_at=_now().replace(microsecond=0) + __import__('datetime').timedelta(seconds=REFRESH_TTL))
    session.add(db_session)
    session.commit()
    access = _sign({'sub': user.id, 'school_id': user.school_id, 'role': user.role, 'iat': now, 'exp': now + TOKEN_TTL, 'sid': sid})
    return {'access_token': access, 'token_type': 'bearer', 'expires_in': TOKEN_TTL, 'refresh_token': refresh, 'refresh_expires_in': REFRESH_TTL, 'user': {'id': user.id, 'name': user.name, 'role': user.role, 'school_id': user.school_id}}

bearer = HTTPBearer(auto_error=False)

def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), session: Session = Depends(db)):
    if not creds:
        raise HTTPException(401, 'Authentication required')
    payload = _decode(creds.credentials)
    sid = payload.get('sid')
    user = session.get(User, payload['sub'])
    auth_session = session.get(AuthSession, sid) if sid else None
    if not user or not auth_session or auth_session.user_id != user.id or auth_session.school_id != user.school_id or auth_session.revoked_at is not None or auth_session.expires_at <= _now():
        raise HTTPException(401, 'Session is no longer valid')
    if user.role != payload['role']:
        raise HTTPException(401, 'Session is no longer valid')
    return user

def current_session(creds: HTTPAuthorizationCredentials = Depends(bearer), session: Session = Depends(db)):
    if not creds:
        raise HTTPException(401, 'Authentication required')
    payload = _decode(creds.credentials)
    sid = payload.get('sid')
    auth_session = session.get(AuthSession, sid) if sid else None
    if not auth_session or auth_session.revoked_at is not None or auth_session.expires_at <= _now():
        raise HTTPException(401, 'Session is no longer valid')
    return auth_session

def require_roles(*roles):
    def dep(user=Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, 'Insufficient permission')
        return user
    return dep

def set_credential(data: CredentialIn, session: Session, actor=None):
    user = session.get(User, data.user_id)
    if not user: raise HTTPException(404, 'User not found')
    if actor is not None and actor.role != 'SUPER_ADMIN' and actor.school_id != user.school_id:
        raise HTTPException(403, 'School scope violation')
    item = session.get(AuthCredential, data.user_id)
    if item: item.password_hash = _hash_password(data.password)
    else: session.add(AuthCredential(user_id=data.user_id, password_hash=_hash_password(data.password)))
    # Credential changes invalidate all existing sessions for the target user.
    session.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).update({'revoked_at': _now()}, synchronize_session=False)
    session.commit()
    return {'user_id': user.id, 'status': 'credential_set', 'sessions_revoked': True}

# In-process limiter for the RC. Production should use a shared store (e.g. Redis) behind the same interface.
_login_failures: dict[str, list[float]] = {}
RATE_WINDOW = int(os.getenv('APJ_LOGIN_RATE_WINDOW', '300'))
RATE_LIMIT = int(os.getenv('APJ_LOGIN_RATE_LIMIT', '10'))

def _rate_key(user_id: int) -> str:
    return f'user:{user_id}'

def _check_login_rate(user_id: int):
    now = time.time(); key = _rate_key(user_id)
    values = [t for t in _login_failures.get(key, []) if now - t < RATE_WINDOW]
    _login_failures[key] = values
    if len(values) >= RATE_LIMIT:
        raise HTTPException(429, 'Too many failed login attempts; try again later')

def _record_login_failure(user_id: int):
    now = time.time(); key = _rate_key(user_id)
    values = [t for t in _login_failures.get(key, []) if now - t < RATE_WINDOW]
    values.append(now); _login_failures[key] = values

def login(data: LoginIn, session: Session):
    _check_login_rate(data.user_id)
    user = session.get(User, data.user_id)
    cred = session.get(AuthCredential, data.user_id)
    if not user or not cred or not _verify_password(data.password, cred.password_hash):
        _record_login_failure(data.user_id)
        raise HTTPException(401, 'Invalid credentials')
    _login_failures.pop(_rate_key(data.user_id), None)
    return _issue_session(user, session)

def refresh(data: RefreshIn, session: Session):
    token_hash = _hash_refresh(data.refresh_token)
    auth_session = session.query(AuthSession).filter_by(refresh_hash=token_hash).first()
    if not auth_session or auth_session.revoked_at is not None or auth_session.expires_at <= _now():
        raise HTTPException(401, 'Invalid or expired refresh token')
    user = session.get(User, auth_session.user_id)
    if not user or user.school_id != auth_session.school_id:
        raise HTTPException(401, 'Session is no longer valid')
    # Rotate: the presented refresh token becomes unusable immediately.
    new_refresh = secrets.token_urlsafe(48)
    auth_session.refresh_hash = _hash_refresh(new_refresh)
    auth_session.refresh_rotated_at = _now()
    session.commit()
    now = int(time.time())
    access = _sign({'sub': user.id, 'school_id': user.school_id, 'role': user.role, 'iat': now, 'exp': now + TOKEN_TTL, 'sid': auth_session.id})
    return {'access_token': access, 'token_type': 'bearer', 'expires_in': TOKEN_TTL, 'refresh_token': new_refresh, 'refresh_expires_in': max(0, int((auth_session.expires_at - _now()).total_seconds()))}

def logout(auth_session: AuthSession, session: Session):
    auth_session.revoked_at = _now()
    session.commit()
    return {'status': 'logged_out'}

def require_school_access(user, school_id: int):
    if user.role == 'SUPER_ADMIN': return
    if user.school_id != school_id: raise HTTPException(403, 'School scope violation')

def require_any_role(*roles):
    return require_roles(*roles)
