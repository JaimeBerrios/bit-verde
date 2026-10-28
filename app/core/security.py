import secrets
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.core.config import settings

basic = HTTPBasic()

def staff(credentials: HTTPBasicCredentials = Depends(basic)):
    valid_user = secrets.compare_digest(credentials.username.encode(), settings.staff_username.encode())
    valid_password = secrets.compare_digest(credentials.password.encode(), settings.staff_password.encode())
    if not settings.staff_password or not (valid_user and valid_password):
        raise HTTPException(401, "Credenciales incorrectas o acceso no configurado", headers={"WWW-Authenticate": "Basic"})

def same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Origen no permitido")
