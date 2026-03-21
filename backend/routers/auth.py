# 📄 backend/routers/auth.py
"""
Autenticación del panel admin con JWT.
POST   /auth/login          → obtener token
GET    /auth/me             → usuario actual
GET    /auth/users          → listar usuarios (solo admin)
POST   /auth/users          → crear usuario  (solo admin)
PUT    /auth/users/{id}     → editar usuario (solo admin)
DELETE /auth/users/{id}     → eliminar usuario (solo admin)
"""
from datetime  import datetime
from typing    import Optional
from fastapi   import APIRouter, Depends, HTTPException, Header
from pydantic  import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db
from models.user     import User
from services.auth   import (
    verify_password, hash_password,
    create_token, get_user_from_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────

class LoginIn(BaseModel):
    username: str
    password: str

class UserIn(BaseModel):
    username:  str
    full_name: Optional[str]  = ""
    password:  Optional[str]  = ""
    role:      str            = "viewer"
    is_active: bool           = True

class UserUpdate(BaseModel):
    full_name: Optional[str]  = None
    password:  Optional[str]  = None
    role:      Optional[str]  = None
    is_active: Optional[bool] = None


# ── Dependency: obtener usuario autenticado ───────────────────────

def get_current_user(
    authorization: str = Header(default=""),
    db: Session        = Depends(get_db),
) -> User:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token requerido")
    user = get_user_from_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol admin")
    return user


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.username == body.username,
        User.is_active == True,
    ).first()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    token = create_token(user.id, user.username, user.role)
    print(f"  🔑  Login: {user.username} ({user.role})")

    return {
        "token": token,
        "user":  user.to_dict(),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user.to_dict()


@router.get("/users")
def list_users(
    _:  User    = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [u.to_dict() for u in users]


@router.post("/users", status_code=201)
def create_user(
    body: UserIn,
    _:    User    = Depends(require_admin),
    db:   Session = Depends(get_db),
):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    if not body.password:
        raise HTTPException(status_code=400, detail="La contraseña es obligatoria")

    u = User(
        username=       body.username,
        full_name=      body.full_name or "",
        hashed_password=hash_password(body.password),
        role=           body.role,
        is_active=      body.is_active,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u.to_dict()


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    body:    UserUpdate,
    _:       User    = Depends(require_admin),
    db:      Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if body.full_name is not None:
        u.full_name = body.full_name
    if body.password:
        u.hashed_password = hash_password(body.password)
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active

    u.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(u)
    return u.to_dict()


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current: User    = Depends(require_admin),
    db:      Session = Depends(get_db),
):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")

    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    db.delete(u)
    db.commit()
    return {"ok": True, "deleted": user_id}