import csv, os
from .database import engine, SessionLocal, Base
from . import models
from sqlalchemy.orm import Session
from datetime import datetime

def create_all():
    Base.metadata.create_all(bind=engine)

def populate_from_csv(rooms_csv='backend/rooms.csv', timetable_csv='backend/timetable.csv'):
    create_all()
    db = SessionLocal()
    # Always reload from CSV: clear existing data
    db.query(models.Occupancy).delete()
    db.query(models.Timetable).delete()
    db.query(models.Room).delete()
    db.commit()
    if not os.path.exists(rooms_csv) or not os.path.exists(timetable_csv):
        print('CSV files missing. Run generator script first.')
        return
    with open(rooms_csv, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = models.Room(
                room_id=row.get('room_id'),
                block=row.get('block'),
                capacity=int(row.get('capacity') or 0),
                type=row.get('type') or 'lecture',
                AC=row.get('AC') or 'No',
                lat=float(row.get('lat') or 0.0),
                lon=float(row.get('lon') or 0.0),
                amenities=row.get('amenities') or ''
            )
            db.add(r)
    db.commit()
    print('Loaded rooms.')
    with open(timetable_csv, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = models.Timetable(
                room_id=row.get('room_id'),
                day=row.get('day'),
                slot=int(row.get('slot') or 0),
                course=row.get('course') or '-'
            )
            db.add(t)
    db.commit()
    print('Loaded timetable.')
