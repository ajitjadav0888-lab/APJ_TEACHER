from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import db
from auth import LoginIn, CredentialIn, RefreshIn, set_credential, login, current_user, current_session, refresh, logout

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])

@router.post('/credentials')
def credentials(data: CredentialIn, session: Session = Depends(db), user=Depends(current_user)):
    if user.role not in {'ADMIN'}:
        from fastapi import HTTPException
        raise HTTPException(403, 'Only ADMIN can provision credentials')
    return set_credential(data, session, actor=user)

@router.get('/debug-login')
def debug_login(session: Session = Depends(db)):
    from auth import AuthCredential, _verify_password
    c = session.query(AuthCredential).filter_by(user_id=1).first()
    return {
        "credential_found": bool(c),
        "password_verify": _verify_password("APJTeacher2026", c.password_hash) if c else False,
        "hash_prefix": c.password_hash[:12] if c else None
    }

@router.post('/login')
def do_login(data: LoginIn, session: Session = Depends(db)):
    return login(data, session)

@router.post('/refresh')
def do_refresh(data: RefreshIn, session: Session = Depends(db)):
    return refresh(data, session)

@router.post('/logout')
def do_logout(auth_session=Depends(current_session), session: Session = Depends(db)):
    return logout(auth_session, session)

@router.get('/me')
def me(user=Depends(current_user)):
    return {'id': user.id, 'name': user.name, 'role': user.role, 'school_id': user.school_id}
