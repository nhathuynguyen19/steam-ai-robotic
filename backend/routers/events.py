from fastapi import APIRouter
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
import models, schemas, database
import core.security as security
from schemas import EventRole
from datetime import datetime, date, time

router = APIRouter(
    prefix="/events",
    tags=["events"],
)

# --- EVENT ENDPOINTS (Admin Create) ---
@router.post("", response_model=schemas.EventResponse)
def create_event(
    event: schemas.EventCreate, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_admin_user)
):
    new_event = models.Event(**event.dict())
    try:
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error creating event: " + str(e))
    
    return new_event

@router.get("", response_model=list[schemas.EventResponse])
def read_events(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db), current_user = Depends(security.get_current_user)):
    events = db\
        .query(models.Event)\
        .options(joinedload(models.Event.participants))\
        .offset(skip)\
        .limit(limit)\
        .all()
    return events

# --- USER-EVENT ACTION (User tham gia sự kiện) ---
@router.post("/{event_id}/join/")
def join_event(
    join_request: schemas.JoinEventRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    # 1. Check event tồn tại
    event = db.query(models.Event).filter(models.Event.event_id == join_request.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # 2. Check đã tham gia chưa
    existing_link = db.query(models.UserEvent).filter(
        models.UserEvent.user_id == current_user.user_id,
        models.UserEvent.event_id == join_request.event_id
    ).first()
    if existing_link:
        raise HTTPException(status_code=400, detail="User already joined this event")
    
    # kiem tra so luong nguoi tham gia du thi khoa event
    participant_count = db.query(models.UserEvent).filter(
        models.UserEvent.event_id == join_request.event_id
    ).count()
    if participant_count >= event.max_user_joined:
        raise HTTPException(status_code=400, detail="Event has reached maximum number of participants")

    # 3. Tạo link
    user_event = models.UserEvent(user_id=current_user.user_id, event_id=join_request.event_id, role=join_request.role)
    
    try:
        db.add(user_event)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error joining event: " + str(e))
    
    return {"detail": "Joined event successfully"}

# huy tham gia
@router.post("/{event_id}/leave/")
def leave_event(
    event_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    # 1. Check event tồn tại
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # 2. Check đã tham gia chưa
    existing_link = db.query(models.UserEvent).filter(
        models.UserEvent.user_id == current_user.user_id,
        models.UserEvent.event_id == event_id
    ).first()
    if not existing_link:
        raise HTTPException(status_code=400, detail="User has not joined this event")
    
    # 3. Xoá link
    try:
        db.delete(existing_link)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error leaving event: " + str(e))
    
    return {"detail": "Left event successfully"}

# danh dau da tham gia
@router.post("/{event_id}/attend/")
def attend_event(
    event_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    # 1. Check event tồn tại
    event = db.query(models.Event).filter(models.Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # 2. Check đã tham gia chưa
    existing_link = db.query(models.UserEvent).filter(
        models.UserEvent.user_id == current_user.user_id,
        models.UserEvent.event_id == event_id
    ).first()
    if not existing_link:
        raise HTTPException(status_code=400, detail="User has not joined this event")
    
    # kiem tra su kien ket thuc chua
    now = datetime.now()
    event_end_time = datetime.combine(event.day_start, time(hour=event.to_time // 100, minute=event.to_time % 100))
    if now < event_end_time:
        raise HTTPException(status_code=400, detail="Event has not ended yet. Cannot mark attendance.")
    
    # 3. Cập nhật trạng thái tham gia
    existing_link.status = "attended"
    db.add(existing_link)
    db.commit()
    
    return {"detail": "Attendance marked successfully"}