from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.core.campaign import Category, COLLECTION_POINT
from app.core.security import staff
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

def page(request, name):
    return templates.TemplateResponse(request=request, name=name+".html", context={"public_url": settings.public_url, "categories": list(Category), "collection_point": COLLECTION_POINT, "trivia_goal_seconds": 45})

@router.get("/")
def index(request: Request): return page(request, "index")
@router.get("/registro")
def registration(request: Request): return page(request, "registro")
@router.get("/dashboard")
def dashboard(request: Request): return page(request, "dashboard")
@router.get("/staff", dependencies=[Depends(staff)])
def staff_page(request: Request): return page(request, "staff")
