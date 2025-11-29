from datetime import datetime, timedelta
from typing import Annotated
from fastapi import Depends, HTTPException, status, APIRouter, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# from jose import JWTError, jwt
# from passlib.context import CryptContext
from sqlalchemy.orm import Session
# from sqlalchemy.exc import IntegrityError
import models, schemas, database
from dotenv import load_dotenv
import os
# from utils.email_utils import send_verification_email
import core.security as security

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

@router.post("/signin/", response_model=schemas.Token)
async def signin_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(database.get_db)
):
    # 1. Tìm user theo Email
    # Mặc dù biến tên là form_data.username (do chuẩn OAuth2 bắt buộc), 
    # nhưng người dùng sẽ nhập Email vào đây.
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    # 2. Xử lý logic: Chưa có user VÀ Hệ thống đang rỗng (Lần đầu tiên chạy)
    if not user:
        # Đếm tổng số user đang có
        user_count = db.query(models.User).count()
        
        if user_count == 0:
            # === AUTO REGISTER ADMIN ===
            # Đây là người dùng đầu tiên của hệ thống
            hashed_password = security.get_password_hash(form_data.password)
            
            user = models.User(
                email=form_data.username,
                hashed_password=hashed_password,
                role=schemas.UserRole.ADMIN.value, # Set quyền Admin cao nhất
                status=True,                 # Kích hoạt luôn, không cần verify email
                full_name="Super Admin"      # Tên mặc định (tùy chọn)
            )
            try:
                db.add(user)
                db.commit()
                db.refresh(user)
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=400, detail="Error creating admin user: " + str(e))
            # Sau bước này, 'user' đã tồn tại và hợp lệ, code sẽ chạy tiếp xuống dưới để tạo token
        else:
            # User không tồn tại và hệ thống đã có người khác rồi -> Lỗi đăng nhập
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # 3. Nếu user đã tồn tại -> Verify password
        if not security.verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # 3. Kiểm tra đã kích hoạt tài khoản chưa
    if not user.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is not active. Please check your email to verify.",
        )

    # 4. Tạo Token
    access_token = security.create_access_token(
        data={"sub": user.email}, # Lưu email vào trong token
        expires_delta=timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# @router.get("/verify/")
# async def verify_email(token: str, db: Session = Depends(database.get_db)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_400_BAD_REQUEST,
#         detail="Could not validate credentials or token expired",
#     )
    
#     try:
#         # token decode
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         email: str = payload.get("sub")
#         token_type: str = payload.get("type")
#         if email is None or token_type != "verification":
#             raise credentials_exception
#     except JWTError:
#         raise credentials_exception
    
#     # Tìm user trong DB
#     user = db.query(models.User).filter(models.User.email == email).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
        
#     # Check if already activated
#     if user.status:
#         return {"message": "Account already activated"}
    
#     # activate user
#     user.status = True
#     db.commit()
    
#     return {"message": "Account activated successfully. You can now login."}


# @router.post("/signup/", response_model=schemas.UserResponse)
# async def create_user(
#     user: schemas.UserRegister, 
#     background_tasks: BackgroundTasks, # Sử dụng BackgroundTasks để gửi mail ko bị lag
#     db: Session = Depends(database.get_db)
# ):
#     # create new user
#     new_user = models.User(
#         email=user.email, 
#         hashed_password=get_password_hash(user.password),
#         status=False  # Đảm bảo status là False
#     )
    
#     # insert user to DB
#     try:
#         db.add(new_user)
#         db.commit()
#         db.refresh(new_user)
#     except IntegrityError:
#         db.rollback()
#         raise HTTPException(status_code=400, detail="Email already registered")
    
#     # create verification token
#     verification_token = create_access_token(
#         data={"sub": new_user.email, "type": "verification"}, 
#         expires_delta=timedelta(minutes=30) # Link sống 30 phút
#     )
    
#     # send mail in background
#     background_tasks.add_task(send_verification_email, new_user.email, verification_token)
    
#     return new_user