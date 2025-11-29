from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List
from datetime import date
import enum
import re

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    
class EventRole(str, enum.Enum):
    INSTRUCTOR = "instructor"
    TA = "teaching_assistant"

# --- USER SCHEMAS ---
class UserBase(BaseModel):
    full_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = Field(None, pattern=r"^0\d{9}$") # Regex: Bắt đầu bằng 0, 10 số
    status: bool = True
    role: str = UserRole.USER
    name_bank: Optional[str] = None
    bank_number: Optional[str] = None

    @field_validator('role')
    def role_must_be_valid(cls, v):
        if v not in [UserRole.USER, UserRole.ADMIN]:
            raise ValueError('Role must be user or admin')
        return v
    
    class Config:
        from_attributes = True
        str_strip_whitespace = True

class UserResponse(UserBase):
    user_id: int
    
    class Config:
        from_attributes = True
        
# 1. Thêm Schema mới chuyên dùng cho Đăng ký
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    re_password: str = Field(..., min_length=6)
    
    @field_validator('email')
    @classmethod
    def validate_gmail(cls, v: str):
        if not v.endswith("@gmail.com"):
            raise ValueError("Hệ thống chỉ chấp nhận tài khoản Gmail (@gmail.com)")
        return v
    
    @model_validator(mode='after')
    def passwords_match(self):
        if self.password != self.re_password:
            raise ValueError('Passwords do not match')
        return self
    
    @field_validator('password')
    def validate_password_strength(cls, v: str):
        if len(v) < 8:
             raise ValueError('Mật khẩu phải có ít nhất 8 ký tự')
        if not re.search(r"\d", v):
            raise ValueError('Mật khẩu phải chứa ít nhất một chữ số')
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError('Mật khẩu phải chứa ít nhất một chữ cái')
        return v
    
# Change Password Schema
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)

# --- EVENT SCHEMAS ---
class EventBase(BaseModel):
    name: str
    day_start: date
    from_time: int = Field(..., ge=0, le=2359, description="Format HHMM, e.g., 830 for 08:30")
    to_time: int = Field(..., ge=0, le=2359)
    number_of_student: int = Field(0, ge=0)
    max_user_joined: int = Field(..., ge=1)
    status: str = "upcoming"
    school_name: Optional[str] = None
    
    # validate logic minute hop le
    @field_validator('from_time', 'to_time')
    @classmethod
    def validate_time_format(cls, v: int):
        minute = v % 100
        if minute >= 60:
            raise ValueError('Minutes must be less than 60')
        return v

    # Validate logic: Giờ kết thúc phải sau giờ bắt đầu
    @model_validator(mode='after')
    def check_time_logic(self):
        if self.to_time <= self.from_time:
            raise ValueError('to_time must be greater than from_time')
        return self
    
    class Config:
        from_attributes = True
        str_strip_whitespace = True

class EventCreate(EventBase):
    @field_validator('day_start')
    def date_must_be_future(cls, v: date):
        # Chỉ chặn nếu là sự kiện mới (logic này tùy nghiệp vụ, thường admin vẫn cần tạo lịch sử)
        if v < date.today():
            raise ValueError('Ngày bắt đầu sự kiện không thể ở trong quá khứ')
        return v
    pass

class EventResponse(EventBase):
    event_id: int
    participants: List['UserEventLink'] = []
    class Config:
        from_attributes = True

# --- USER_EVENT (Tham gia sự kiện) ---
class UserEventLink(BaseModel):
    user_id: int
    role: str = "participant"

# --- TOKEN ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None # Đổi từ username sang email
    
class JoinEventRequest(BaseModel):
    event_id: int
    role: str = EventRole.TA
    @field_validator('role')
    def validate_role(cls, v):
        if v not in [EventRole.INSTRUCTOR, EventRole.TA]:
            raise ValueError('Role must be instructor or ta')
        return v