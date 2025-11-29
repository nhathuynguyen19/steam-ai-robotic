# from typing import Annotated
from fastapi import FastAPI
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlalchemy.orm import Session, joinedload
import models, schemas, routers.auth as auth, database
# from utils.email_utils import send_verification_email
# from jose import jwt, JWTError
from fastapi.staticfiles import StaticFiles # <--- Import cái này
from fastapi.openapi.docs import get_redoc_html # <--- Import cái này
# from models import EventRole
from routers import auth, users, events

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(docs_url="/docs", redoc_url=None)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(events.router)

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )

