from fastapi import APIRouter
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
import models, schemas, database
import core.security as security

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

@router.get("/me/", response_model=schemas.UserResponse)
async def read_users_me(current_user: Annotated[models.User, Depends(security.get_current_user)]):
    return current_user

@router.put("/me/change-password/")
async def change_password(
    password_data: schemas.ChangePasswordRequest,
    current_user: Annotated[models.User, Depends(security.get_current_user)],
    db: Session = Depends(database.get_db)
):
    # 1. Kiểm tra mật khẩu hiện tại
    if not security.verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    # 2. Cập nhật mật khẩu mới
    current_user.hashed_password = security.get_password_hash(password_data.new_password)
    db.add(current_user)
    db.commit()
    
    return {"message": "Password changed successfully"}