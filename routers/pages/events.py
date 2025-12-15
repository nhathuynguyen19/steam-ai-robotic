from fastapi import APIRouter, Request, Depends, Form, status, HTTPException, Query
from fastapi.responses import RedirectResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, not_
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Annotated, Optional, List
from datetime import date
import database
import models
import schemas
import helpers.security as security
from fastapi import HTTPException
from routers.api.events import PERIOD_START_TIMES, PERIOD_END_TIMES
from fastapi.responses import HTMLResponse
from models import User, Event, UserEvent, EventRole
from helpers.security import get_current_admin_from_cookie


# Định nghĩa đường dẫn tới thư mục templates
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(
    prefix="/events",
    tags=["pages_events"] 
)

# 1. GET: Hiển thị trang tạo sự kiện (Chỉ Admin)
@router.get("/create")
async def get_event_create_page(
    request: Request,
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    if not isinstance(current_user, models.User):
        return current_user 
    
    return templates.TemplateResponse(
        "pages/create_event.html",
        {
            "request": request,
            "user": current_user,
            "error": None,
            # [MỚI] Truyền danh sách giờ xuống template
            "period_start_times": PERIOD_START_TIMES,
            "period_end_times": PERIOD_END_TIMES
        }
    )

# 2. POST: Xử lý form tạo sự kiện (Chỉ Admin)
@router.post("/create")
async def create_event_action(
    request: Request,
    name: Annotated[str, Form()],
    day_start: Annotated[date, Form()],
    start_period: Annotated[int, Form()],
    end_period: Annotated[int, Form()],
    number_of_student: Annotated[int, Form()],
    # max_user_joined: Annotated[int, Form()],
    max_instructor: Annotated[int, Form()],
    max_teaching_assistant: Annotated[int, Form()],
    school_name: Annotated[Optional[str], Form()] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    try:
        # Sử dụng Schema để validate dữ liệu (logic start < end period đã có trong schema)
        event_data = schemas.EventCreate(
            name=name,
            day_start=day_start,
            start_period=start_period,
            end_period=end_period,
            number_of_student=number_of_student, # Map vào schema
            max_user_joined=max_instructor + max_teaching_assistant,
            school_name=school_name,
            max_instructor=max_instructor,
            max_teaching_assistant=max_teaching_assistant,
        )
        
        # Tạo model và lưu vào DB
        new_event = models.Event(**event_data.model_dump())
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        
        # Thành công: Redirect về trang danh sách sự kiện (hoặc trang chi tiết)
        # 303 See Other là chuẩn cho redirect sau khi POST
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    except ValueError as e:
        # Lỗi Validate (VD: tiết kết thúc < tiết bắt đầu): Trả lại form kèm thông báo lỗi
        return templates.TemplateResponse(
            "pages/create_event.html",
            {
                "request": request,
                "user": current_user,
                "error": str(e), # Hiển thị lỗi ra template
                # Có thể trả lại các giá trị đã nhập để user không phải gõ lại (optional)
            }
        )
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            "pages/create_event.html",
            {
                "request": request,
                "user": current_user,
                "error": "Đã xảy ra lỗi hệ thống: " + str(e)
            }
        )
        
# 3. GET: Hiển thị trang cập nhật sự kiện
@router.get("/{event_id}/edit")
async def get_event_edit_page(
    request: Request,
    event_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    if not isinstance(current_user, models.User):
        return current_user 

    # Tìm sự kiện theo ID
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện")

    return templates.TemplateResponse(
        "pages/edit_event.html", # File template này sẽ tạo ở bước 3
        {
            "request": request,
            "user": current_user,
            "event": event,
            "error": None,
            # [MỚI] Truyền danh sách giờ xuống template
            "period_start_times": PERIOD_START_TIMES,
            "period_end_times": PERIOD_END_TIMES
        }
    )

# 4. POST: Xử lý cập nhật sự kiện
@router.post("/{event_id}/edit")
async def update_event_action(
    request: Request,
    event_id: int,
    name: Annotated[str, Form()],
    day_start: Annotated[date, Form()],
    start_period: Annotated[int, Form()],
    end_period: Annotated[int, Form()],
    number_of_student: Annotated[int, Form()],
    # [THAY ĐỔI] Thay max_user_joined bằng 2 trường riêng biệt
    max_instructor: Annotated[int, Form()],
    max_teaching_assistant: Annotated[int, Form()],
    school_name: Annotated[Optional[str], Form()] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_from_cookie)
):
    if not isinstance(current_user, models.User):
        return current_user

    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện")

    try:
        # Tự động tính tổng max_user_joined
        calculated_max_joined = max_instructor + max_teaching_assistant
        
        # Validate dữ liệu bằng Schema
        event_data = schemas.EventCreate(
            name=name,
            day_start=day_start,
            start_period=start_period,
            end_period=end_period,
            number_of_student=number_of_student,
            max_user_joined=calculated_max_joined, # Gán giá trị tính toán
            max_instructor=max_instructor,         # Gán giá trị riêng
            max_teaching_assistant=max_teaching_assistant, # Gán giá trị riêng
            school_name=school_name
        )

        # Cập nhật các trường vào DB
        event.name = event_data.name
        event.day_start = event_data.day_start
        event.start_period = event_data.start_period
        event.end_period = event_data.end_period
        event.number_of_student = event_data.number_of_student
        
        event.max_instructor = event_data.max_instructor
        event.max_teaching_assistant = event_data.max_teaching_assistant
        event.max_user_joined = event_data.max_user_joined
        
        event.school_name = event_data.school_name
        
        db.commit()
        db.refresh(event)
        
        # Redirect về trang chủ hoặc trang chi tiết
        return RedirectResponse(url="/events", status_code=status.HTTP_303_SEE_OTHER)

    except ValueError as e:
        return templates.TemplateResponse(
            "pages/edit_event.html",
            {
                "request": request,
                "user": current_user,
                "event": event, # Trả lại event cũ để fill form
                "error": str(e),
                "period_start_times": PERIOD_START_TIMES,
                "period_end_times": PERIOD_END_TIMES
            }
        )
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            "pages/edit_event.html",
            {
                "request": request,
                "user": current_user,
                "event": event,
                "error": "Lỗi hệ thống: " + str(e),
                "period_start_times": PERIOD_START_TIMES,
                "period_end_times": PERIOD_END_TIMES
            }
        ) 

# --- 1. API Trả về giao diện quản lý người tham gia (HTML) ---
@router.get("/partials/events/{event_id}/manage", response_class=HTMLResponse)
async def get_event_participants_manager(
    request: Request, 
    event_id: int, 
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_admin_from_cookie)
):
    if current_user.role != schemas.UserRole.ADMIN.value:
        return Response(content="Unauthorized", status_code=403)

    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        return Response(content="Event not found", status_code=404)

    # Lấy danh sách Instructor và TA
    instructors = db.query(UserEvent).filter(UserEvent.event_id == event_id, UserEvent.role == 'instructor').all()
    tas = db.query(UserEvent).filter(UserEvent.event_id == event_id, UserEvent.role == 'teaching_assistant').all()

    return templates.TemplateResponse("partials/event_participants_manager.html", {
        "request": request,
        "event": event,
        "instructors": instructors,
        "tas": tas,
        "current_instructor_count": len(instructors),
        "current_ta_count": len(tas)
    })
    
    # [QUAN TRỌNG] Thêm Header báo trình duyệt KHÔNG được cache HTML này
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return response

# --- 2. API Xóa User khỏi Event ---
@router.delete("/partials/events/{event_id}/participants/{user_id}", response_class=HTMLResponse)
async def remove_participant(
    request: Request, event_id: int, user_id: int, 
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_admin_from_cookie)
):
    if current_user.role != schemas.UserRole.ADMIN.value:
        return Response(status_code=403)
        
    db.query(UserEvent).filter(UserEvent.event_id == event_id, UserEvent.user_id == user_id).delete()
    db.commit()
    
    # [QUAN TRỌNG] Xóa cache của SQLAlchemy session để lần query tiếp theo lấy data mới nhất
    db.expire_all()
    
    # Reload lại toàn bộ khung quản lý
    return await get_event_participants_manager(request, event_id, db, current_user)

# --- 3. API Lấy danh sách User CHƯA tham gia để hiện Modal (Có phân trang & Search) ---
@router.get("/partials/events/{event_id}/candidates", response_class=HTMLResponse)
async def get_candidate_users(
    request: Request, 
    event_id: int, 
    role_to_add: str, # 'instructor' hoặc 'teaching_assistant'
    q: Optional[str] = None,
    page: int = 1,
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_admin_from_cookie)
):
    if current_user.role != schemas.UserRole.ADMIN.value: return Response(status_code=403)
    
    limit = 10
    skip = (page - 1) * limit

    # Lấy danh sách ID đã tham gia
    # joined_ids = db.query(UserEvent.user_id).filter(UserEvent.event_id == event_id).subquery()

    # [ĐÚNG - Sửa lại như sau]
    # Xóa .subquery(), để nguyên câu query. SQLAlchemy sẽ tự động biên dịch nó thành sub-select chuẩn.
    joined_ids = db.query(models.UserEvent.user_id).filter(models.UserEvent.event_id == event_id)
    
    # Query user chưa tham gia
    query = db.query(models.User).filter(
        not_(models.User.user_id.in_(joined_ids)), 
        models.User.is_deleted == False
    )

    if q:
        search = f"%{q}%"
        query = query.filter(User.full_name.ilike(search) | User.email.ilike(search))

    total = query.count()
    users = query.offset(skip).limit(limit).all()
    total_pages = (total + limit - 1) // limit

    return templates.TemplateResponse("partials/modal_select_users.html", {
        "request": request,
        "event_id": event_id,
        "users": users,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "role_to_add": role_to_add
    })

# --- 4. API Thêm Users vào Event (Xử lý Logic & Validate) ---
@router.post("/partials/events/{event_id}/participants", response_class=HTMLResponse)
async def add_participants(
    request: Request,
    event_id: int,
    user_ids: List[int] = Form(...), # Nhận list ID từ checkbox
    role: str = Form(...),
    db: Session = Depends(database.get_db),
    current_user: User = Depends(get_current_admin_from_cookie)
):
    if current_user.role != schemas.UserRole.ADMIN.value: return Response(status_code=403)

    event = db.query(Event).filter(Event.event_id == event_id).first()
    
    # Kiểm tra số lượng
    current_count = db.query(UserEvent).filter(UserEvent.event_id == event_id, UserEvent.role == role).count()
    
    max_allowed = event.max_instructor if role == 'instructor' else event.max_teaching_assistant
    # Handle trường hợp max_instructor có thể là None (nếu model cho phép) hoặc 0
    max_allowed = max_allowed if max_allowed is not None else 999 

    # Nếu vượt quá giới hạn -> Trả về lỗi vào div #form-errors (Không đóng modal)
    if current_count + len(user_ids) > max_allowed:
        error_msg = f"Đã chọn {len(user_ids)} người. Tổng sẽ là {current_count + len(user_ids)}, vượt quá giới hạn ({max_allowed}). Vui lòng bỏ bớt."
        return Response(
            content=f"""
            <div class="alert alert-danger d-flex align-items-center mb-0">
                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                <div>{error_msg}</div>
            </div>
            """,
            media_type="text/html"
        )

    # Thêm user
    for uid in user_ids:
        new_member = UserEvent(event_id=event_id, user_id=uid, role=role, status="registered")
        db.add(new_member)
    
    db.commit()
    
    # [QUAN TRỌNG] Làm mới session
    db.expire_all()
    
    # 3. Chuẩn bị dữ liệu để render lại danh sách quản lý (Modal 1)
    instructors = db.query(models.UserEvent).filter(models.UserEvent.event_id == event_id, models.UserEvent.role == 'instructor').all()
    tas = db.query(models.UserEvent).filter(models.UserEvent.event_id == event_id, models.UserEvent.role == 'teaching_assistant').all()

    # Render template Modal 1 (Manager)
    # Lưu ý: 'templates' phải là biến Jinja2Templates đã khai báo ở đầu file
    manager_html = templates.get_template("partials/event_participants_manager.html").render({
        "request": request,
        "event": event,
        "instructors": instructors,
        "tas": tas,
        "current_instructor_count": len(instructors),
        "current_ta_count": len(tas)
    })

    # 4. Trả về Response kết hợp (OOB Swap)
    # - Cập nhật nội dung Modal 1 (#manageMembersModalBody)
    # - Xóa thông báo lỗi cũ (nếu có)
    # - Chạy script đóng Modal 2 (#addParticipantModal)
    
    combined_response = f"""
    <div id="manageMembersModalBody" hx-swap-oob="true">
        {manager_html}
    </div>

    <div id="form-errors" hx-swap-oob="true"></div>

    <script>
        // Đóng modal chọn user
        var selectModalEl = document.getElementById('addParticipantModal');
        var selectModal = bootstrap.Modal.getInstance(selectModalEl);
        if (selectModal) {{ selectModal.hide(); }}
        
        // [QUAN TRỌNG] Mở lại modal quản lý (vì nó đã bị ẩn khi mở modal chọn user)
        var manageModalEl = document.getElementById('manageMembersModal');
        var manageModal = bootstrap.Modal.getOrCreateInstance(manageModalEl);
        manageModal.show();

        // Fix các lỗi backdrop còn sót lại của Bootstrap
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        // Thêm lại backdrop mới cho modal vừa mở
        if (!document.querySelector('.modal-backdrop')) {{
             var backdrop = document.createElement('div');
             backdrop.className = 'modal-backdrop fade show';
             document.body.appendChild(backdrop);
        }}
        document.body.classList.add('modal-open');
        document.body.style.overflow = 'hidden';
    </script>
    """
    
    return Response(content=combined_response, media_type="text/html")