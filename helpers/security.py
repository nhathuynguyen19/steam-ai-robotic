import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
import database, models, schemas
from sqlalchemy.orm import Session
import models, schemas, database
import os
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime
from zoneinfo import ZoneInfo

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/signin/", auto_error=False)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        
        expire = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None) + expires_delta
    else:
        expire = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Hàm này dùng để lấy user từ cookie (Dùng cho các trang HTML)
async def get_user_from_cookie(
    request: Request, 
    db: Session = Depends(database.get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        return None

    # Xử lý prefix Bearer nếu có
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email:
            user = db.query(models.User).filter(models.User.email == email).first()
            if user and user.status:
                return user
    except Exception:
        pass
    
    return None

async def get_current_admin_from_cookie(
    request: Request,
    user: Annotated[models.User | None, Depends(get_user_from_cookie)]
):
    """
    Dependency bắt buộc phải có Cookie hợp lệ VÀ là Admin.
    Dùng cho các route bảo mật (VD: Tạo sự kiện).
    """
    # 1. Kiểm tra đăng nhập
    if not user:
        # Nếu chưa đăng nhập -> Redirect về trang login thay vì báo lỗi 401 JSON
        # (Vì đây là truy cập trình duyệt)
        return RedirectResponse(url="/auth/signin", status_code=status.HTTP_302_FOUND)
        # Hoặc nếu muốn báo lỗi chuẩn: raise HTTPException(status_code=401)

    # 2. Kiểm tra quyền Admin
    if user.role != schemas.UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Truy cập bị từ chối. Bạn không phải là Admin."
        )
    
    return user