from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from ...core.security import create_admin_jwt, settings

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    admin_key: str

@router.post("/login")
async def login(body: LoginRequest, response: Response):
    # 1. Verifica la chiave master
    if body.admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid admin key"
        )
    
    # 2. Genera il JWT
    token = create_admin_jwt("admin_user")
    
    # 3. Imposta il Cookie HttpOnly
    response.set_cookie(
        key="admin_access_token",
        value=token,
        httponly=True,    # Fondamentale: impedisce accesso da JS (XSS)
        secure=False,      # Obbligatorio in produzione con HTTPS
        samesite="strict",# Protegge da CSRF
        max_age=28800,     # 8 ore (in secondi)
        path="/",

    )
    
    return {"message": "Login successful"}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("admin_access_token")
    return {"message": "Logged out"}