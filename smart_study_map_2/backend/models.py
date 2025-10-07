from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, unique=True, index=True)
    block = Column(String, index=True)
    capacity = Column(Integer)
    type = Column(String, default="lecture")
    AC = Column(String, default="No")
    lat = Column(Float)
    lon = Column(Float)
    amenities = Column(String, default="")
    def __repr__(self):
        return f"<Room {self.room_id}>"

class Timetable(Base):
    __tablename__ = "timetables"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, index=True)
    day = Column(String, index=True)  # e.g., Mon, Tue
    slot = Column(Integer)  # 0..n
    course = Column(String, default='-')

class Occupancy(Base):
    __tablename__ = "occupancies"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    occupancy_level = Column(Integer)  # percent 0-100
