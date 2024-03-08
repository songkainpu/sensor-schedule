import threading
import traceback
from typing import Union

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from data_model import EventCyclicScheduler
from my_enum import get_batch_id, EventEnum, SensorEnum
import gevent
from gevent import monkey

monkey.patch_all()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('sqlalchemy.engine')

logger.setLevel(logging.INFO)
# user, password, host, dbname
DATABASE_URI = 'mysql+pymysql://songkai:test@101.43.133.171:3307/embedded_system'

engine = create_engine(DATABASE_URI)

Session = sessionmaker(bind=engine)

ARR_CACHE = []
lock: threading.Lock = threading.Lock()


def save_event(event: EventEnum, simpy_time: Union[float, int], sensor: SensorEnum):
    try:
        with lock:
            global ARR_CACHE
            batch_uuid = get_batch_id()
            ARR_CACHE.append(EventCyclicScheduler(**{
                "batch_uuid": batch_uuid,
                "event": event.name,
                "simpy_time": simpy_time,
                "sensor_name": sensor.name
            }))
            if len(ARR_CACHE) < 10:
                return
            print(f"event_tracking:{event}, simpy_time:{simpy_time}, sensor:{sensor}")
            session: Session = Session()
            session.add_all(ARR_CACHE)
            session.commit()
            session.close()
            ARR_CACHE = []
    except Exception as e:
        logger.error(e)
        traceback.print_exception(e)
        traceback.print_stack()


def final_save_event():
    with lock:
        session: Session = Session()
        session.add_all(ARR_CACHE)
        session.commit()
        session.close()
