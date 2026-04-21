from sqlalchemy import Column, String, Integer, Float
from database import Base

class Event(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True)
    name = Column(String)
    time = Column(String)
    duration = Column(Float)
    zone = Column(Integer)
    risk = Column(Integer)
    image = Column(String)
    status = Column(String, default="In Process")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String)
    password = Column(String)