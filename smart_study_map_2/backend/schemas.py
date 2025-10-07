from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class RoomBase(BaseModel):
    room_id: str
    block: str
    capacity: int
    type: str
    AC: str
    lat: float
    lon: float
    amenities: str

class RoomOut(RoomBase):
    status: str
    occupancy_level: int

class OccupancyIn(BaseModel):
    occupancy_level: int

class OccupancyOut(BaseModel):
    room_id: str
    timestamp: datetime
    occupancy_level: int

class TimetableItem(BaseModel):
    room_id: str
    day: str
    slot: int
    course: str
