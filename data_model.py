from enum import Enum

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class EventCyclicScheduler(Base):
    __tablename__ = 'event_cyclic_scheduler'
    id = Column(Integer, primary_key=True)
    batch_uuid = Column(String(2048))
    event = Column(Integer)
    simpy_time = Column(Integer)
    sensor_name = Column(String(256))
