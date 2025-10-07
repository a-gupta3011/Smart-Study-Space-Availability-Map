from sqlalchemy.orm import Session
from . import models
from datetime import datetime, timedelta, timezone
import random

OCC_THRESHOLD = 30

DAY_NAMES = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

def current_day_slot():
    now = datetime.now(timezone.utc)
    day = DAY_NAMES[now.weekday()]
    slot = now.hour % 10  # simple 10-slot mapping
    return day, slot

def get_rooms(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Room).offset(skip).limit(limit).all()

def get_room_by_id(db: Session, room_id: str):
    return db.query(models.Room).filter(models.Room.room_id == room_id).first()

def add_occupancy(db: Session, room_id: str, occupancy_level: int):
    o = models.Occupancy(room_id=room_id, occupancy_level=occupancy_level)
    db.add(o)
    db.commit()
    db.refresh(o)
    return o

def get_latest_occupancy(db: Session, room_id: str):
    return db.query(models.Occupancy).filter(models.Occupancy.room_id==room_id).order_by(models.Occupancy.timestamp.desc()).first()

def compute_status(db: Session, room):
    # Heuristic: if current time-slot has a timetable entry -> Booked
    day, slot = current_day_slot()
    booked = db.query(models.Timetable).filter(models.Timetable.room_id==room.room_id, models.Timetable.day==day, models.Timetable.slot==slot).first()
    latest = get_latest_occupancy(db, room.room_id)
    level = latest.occupancy_level if latest else 0
    if booked:
        return "Booked", level
    if level > OCC_THRESHOLD:
        return "Free but Occupied ❌", level
    return "Free & Empty ✅", level

def rooms_free_filtered(db: Session, block=None, capacity=None):
    q = db.query(models.Room)
    if block:
        q = q.filter(models.Room.block == block)
    if capacity:
        q = q.filter(models.Room.capacity >= int(capacity))
    results = []
    for r in q.limit(100).all():
        status, level = compute_status(db, r)
        if status.startswith('Free & Empty'):
            results.append((r, status, level))
    return results
