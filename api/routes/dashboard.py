"""
Invoice Generator Dashboard Routes
Serves the web dashboard HTML pages.
Protected pages require authentication via JWT cookie.
"""

from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.auth_service import get_current_user

router = APIRouter()

templates_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# ── Public pages (no auth required) ──────────────────────────

@router.get("/get-started", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Landing / get-started page."""
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Signup page."""
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("signup.html", {"request": request})


# ── Protected pages (auth required) ──────────────────────────

def _auth_or_redirect(request: Request):
    """Return user dict or a redirect response."""
    user = get_current_user(request)
    if not user:
        return None
    return user


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main dashboard page."""
    user = _auth_or_redirect(request)
    if not user:
        return RedirectResponse(url="/get-started", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@router.get("/customers-page", response_class=HTMLResponse)
async def customers_page(request: Request):
    """Customer management page."""
    user = _auth_or_redirect(request)
    if not user:
        return RedirectResponse(url="/get-started", status_code=302)
    return templates.TemplateResponse("customers.html", {"request": request, "user": user})


@router.get("/invoices-page", response_class=HTMLResponse)
async def invoices_page(request: Request):
    """Invoice history page."""
    user = _auth_or_redirect(request)
    if not user:
        return RedirectResponse(url="/get-started", status_code=302)
    return templates.TemplateResponse("invoices.html", {"request": request, "user": user})


@router.get("/dataset-page", response_class=HTMLResponse)
async def dataset_page(request: Request):
    """Dataset viewer page."""
    user = _auth_or_redirect(request)
    if not user:
        return RedirectResponse(url="/get-started", status_code=302)
    return templates.TemplateResponse("dataset.html", {"request": request, "user": user})


@router.get("/settings-page", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Contractor profile settings page."""
    user = _auth_or_redirect(request)
    if not user:
        return RedirectResponse(url="/get-started", status_code=302)
    return templates.TemplateResponse("settings.html", {"request": request, "user": user})


@router.get("/logout")
async def logout(request: Request):
    """Log out and clear cookie."""
    from services.auth_service import clear_auth_cookie
    response = RedirectResponse(url="/get-started", status_code=302)
    clear_auth_cookie(response)
    return response
