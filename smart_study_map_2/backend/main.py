import threading, time, random, os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import models, schemas, crud
from .database import SessionLocal, engine
from .init_db import create_all, populate_from_csv
import uvicorn
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from collections import defaultdict

app = FastAPI(title='Smart Study Map API')

# CORS settings
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Startup event
@app.on_event('startup')
def startup_event():
    create_all()
    t = threading.Thread(target=occupancy_simulator, daemon=True)
    t.start()

# Health check
@app.get('/health')
def health():
    return {'status':'ok'}

# Admin CSV loader
@app.post('/admin/load_csv')
def admin_load_csv(rooms_path: str, timetable_path: str):
    populate_from_csv(rooms_path, timetable_path)
    return {'loaded': True}

# List all rooms
@app.get('/rooms/all', response_model=List[schemas.RoomOut])
def rooms_all(db: Session = Depends(get_db)):
    rooms = db.query(models.Room).all()
    out = []
    for r in rooms:
        status, level = crud.compute_status(db, r)
        out.append({
            'room_id': r.room_id,
            'block': r.block,
            'capacity': r.capacity,
            'type': r.type,
            'AC': r.AC,
            'lat': r.lat,
            'lon': r.lon,
            'amenities': r.amenities,
            'status': status,
            'occupancy_level': level
        })
    return out

# List free rooms
@app.get('/rooms/free', response_model=List[schemas.RoomOut])
def rooms_free(block: str = None, capacity: int = None, db: Session = Depends(get_db)):
    results = crud.rooms_free_filtered(db, block, capacity)
    out = []
    for r, status, level in results:
        out.append({
            'room_id': r.room_id,
            'block': r.block,
            'capacity': r.capacity,
            'type': r.type,
            'AC': r.AC,
            'lat': r.lat,
            'lon': r.lon,
            'amenities': r.amenities,
            'status': status,
            'occupancy_level': level
        })
    return out

# Room detail
@app.get('/rooms/{room_id}')
def room_detail(room_id: str, db: Session = Depends(get_db)):
    r = db.query(models.Room).filter(models.Room.room_id==room_id).first()
    if not r:
        raise HTTPException(status_code=404, detail='Room not found')
    tt = db.query(models.Timetable).filter(models.Timetable.room_id==room_id).all()
    occs = db.query(models.Occupancy).filter(models.Occupancy.room_id==room_id).order_by(models.Occupancy.timestamp.desc()).limit(50).all()
    return {
        'room': {
            'room_id': r.room_id, 'block': r.block, 'capacity': r.capacity,
            'type': r.type, 'AC': r.AC, 'lat': r.lat, 'lon': r.lon, 'amenities': r.amenities
        },
        'timetable': [{'day': t.day, 'slot': t.slot, 'course': t.course} for t in tt],
        'occupancy_history': [{'timestamp': o.timestamp.isoformat(), 'occupancy_level': o.occupancy_level} for o in occs]
    }

# ---- JSON Check-in ----
class CheckinPayload(BaseModel):
    occupancy_level: int

@app.post('/rooms/{room_id}/checkin')
def checkin(room_id: str, payload: CheckinPayload, db: Session = Depends(get_db)):
    r = db.query(models.Room).filter(models.Room.room_id==room_id).first()
    if not r:
        raise HTTPException(status_code=404, detail='Room not found')
    o = crud.add_occupancy(db, room_id, payload.occupancy_level)
    return {'ok': True, 'occupancy_id': o.id}

# Heatmap
@app.get('/analytics/heatmap')
def heatmap(day: str = None, slot: int = None, db: Session = Depends(get_db)):
    blocks = {}
    rooms = db.query(models.Room).all()
    for r in rooms:
        latest = db.query(models.Occupancy).filter(models.Occupancy.room_id==r.room_id).order_by(models.Occupancy.timestamp.desc()).first()
        level = latest.occupancy_level if latest else 0
        blocks.setdefault(r.block, []).append(level)
    agg = [{'block': k, 'avg_occupancy': sum(v)//len(v) if v else 0} for k,v in blocks.items()]
    return agg

# Summary analytics
@app.get('/analytics/summary')
def analytics_summary(db: Session = Depends(get_db)):
    rooms = db.query(models.Room).all()
    total_rooms = len(rooms)
    # Latest occupancy per room
    latest_levels: Dict[str,int] = {}
    for r in rooms:
        latest = db.query(models.Occupancy).filter(models.Occupancy.room_id==r.room_id).order_by(models.Occupancy.timestamp.desc()).first()
        latest_levels[r.room_id] = latest.occupancy_level if latest else 0

    # By block aggregation
    blocks = defaultdict(lambda: { 'rooms':0, 'avg_occupancy':0, 'capacity':0, 'used_capacity_pct':0 })
    for r in rooms:
        b = r.block or 'Unknown'
        blocks[b]['rooms'] += 1
        blocks[b]['capacity'] += int(r.capacity or 0)
        blocks[b]['avg_occupancy'] += latest_levels.get(r.room_id, 0)
    for b, v in blocks.items():
        v['avg_occupancy'] = int(round(v['avg_occupancy'] / max(1, v['rooms'])))
        # capacity utilization percentage = avg occupancy proxy
        v['used_capacity_pct'] = v['avg_occupancy']

    total_capacity = sum(int(r.capacity or 0) for r in rooms)

    # Types breakdown
    types = defaultdict(int)
    for r in rooms:
        types[str(r.type or 'lecture')] += 1

    # Timetable coverage: fraction of lecture rooms with an entry per day/slot
    lecture_ids = set(r.room_id for r in rooms if str(r.type or 'lecture').lower() == 'lecture')
    days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    coverage = { d: [0]*10 for d in days }
    denom = max(1, len(lecture_ids))
    for d in days:
        for s in range(10):
            count = db.query(models.Timetable.room_id).filter(models.Timetable.day==d, models.Timetable.slot==s, models.Timetable.room_id.in_(lecture_ids)).distinct().count()
            coverage[d][s] = int(round((count / denom) * 100))

    # Occupancy insert rate (last 5 minutes)
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=5)
    recent = db.query(models.Occupancy).filter(models.Occupancy.timestamp >= since).all()
    per_min = defaultdict(int)
    for o in recent:
        minute = o.timestamp.replace(second=0, microsecond=0).isoformat()
        per_min[minute] += 1
    inserts_last_5m = sum(per_min.values())

    return {
        'total_rooms': total_rooms,
        'total_capacity': total_capacity,
        'types': types,
        'blocks': [{'block': b, **v} for b,v in sorted(blocks.items())],
        'timetable_coverage_pct': coverage,
        'occupancy_inserts_last_5m': inserts_last_5m,
        'occupancy_inserts_per_minute': per_min,
    }

# Occupancy simulator
def occupancy_simulator():
    from .database import SessionLocal
    db = SessionLocal()
    while True:
        try:
            rooms = db.query(models.Room.room_id).limit(200).all()
            if not rooms:
                time.sleep(2)
                continue
            for rid, in random.sample(rooms, k=min(10, len(rooms))):
                level = max(0, min(100, int(random.gauss(10,20))))
                o = models.Occupancy(room_id=rid, occupancy_level=level)
                db.add(o)
            db.commit()
        except Exception as e:
            print('sim error', e)
        time.sleep(4)

if __name__ == '__main__':
    uvicorn.run('backend.main:app', host='0.0.0.0', port=8000, reload=True)
