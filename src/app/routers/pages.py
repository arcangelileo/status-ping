from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import decode_access_token, get_current_user
from app.models.user import User

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="src/app/templates")


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    # If user is already logged in, redirect to dashboard
    token = request.cookies.get("access_token")
    if token and decode_access_token(token):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "landing.html")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("access_token")
    if token and decode_access_token(token):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html")


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    token = request.cookies.get("access_token")
    if token and decode_access_token(token):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "signup.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})
