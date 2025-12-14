from fastapi import FastAPI, Request
from routers.api import admin, auth, events, users
import models, schemas, routers.api.auth as auth, database
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_redoc_html
from routers.api import users
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from helpers.limiter import limiter
from typing import Annotated
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_redoc_html
from fastapi.templating import Jinja2Templates 
from starlette.middleware.sessions import SessionMiddleware
import helpers.security as security
from routers.pages import auth as auth_page
from routers.pages import base as base_page
from routers.pages import partials as partials_page
from routers.pages import events as events_page
from routers.pages import admin as pages_admin
from routers.pages import profile
from utils import alembic_config

app = FastAPI(docs_url="/docs", 
              redoc_url=None,
              lifespan=alembic_config.lifespan
              )
app.mount("/static", StaticFiles(directory="static"), name="static")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SessionMiddleware, secret_key=security.SECRET_KEY)


# api routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(admin.router)

# pages routers
app.include_router(auth_page.router)
app.include_router(base_page.router)
app.include_router(partials_page.router)
app.include_router(events_page.router)
app.include_router(pages_admin.router)
app.include_router(profile.router)

# ============================
# CUSTOM REDOC
# ============================
@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/js/redoc.standalone.js",
    )
    
# Tạo bảng DB
models.Base.metadata.create_all(bind=database.engine)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Cấu hình CSP:
    # - script-src: Thêm 'unsafe-eval' để sửa lỗi bạn gặp.
    # - Thêm các domain CDN (jsdelivr, unpkg) để load thư viện.
    # - style-src/font-src: Cho phép Bootstrap và Google Fonts.
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "worker-src 'self' blob:;"
    )
    
    response.headers["Content-Security-Policy"] = csp_policy
    return response