import bounded_queue
from enum import Enum
from typing import Union, Tuple, Type

ERROR_RATE = 0.05
class SensorEnum(Enum):
    # 16.436个异常中断  平均每秒产生的
    # 共占用575.26ms
    # 根据阻塞队列 每个设备 局部内存区满的时间都是1s
    # range unit mg
    ACCELEROMETER = (52, 0.05, (-2, 2), -1.9, 1.9, 52)
    # range unit dps
    GYROSCOPE = (52, 0.05, (-60, 60), -50, 50, 52)
    # range unit rH%
    HUMIDITY = (1, 0.05, (30, 70), 40, 60, 1)
    # range unit Celsius
    TEMPERATURE = (1, 0.05, (15, 30), 20, 25, 1)
    # range unit Gauss
    MAGNETOMETER = (40, 0.05, (0, 100), 5, 95, 40)
    # range unit hPa
    PRESSURE = (25, 0.05, (0, 100000), 5, 99995, 25)

    def __init__(self, rate: float, error: float, range_tuple: Tuple[float, float],
                 mini_threshold: Union[int, float], max_threshold: Union[int, float], data_capacity: int):
        """
        :param rate: unitL Hz
        :param error:  unit 1
        :param range_tuple: it depends on the enum
        :param mini_threshold
        :param max_threshold
        """
        self.rate = rate
        self.error = error
        self.range_tuple = range_tuple
        self.mini_threshold = mini_threshold
        self.max_threshold = max_threshold
        self.data_capacity = data_capacity


class DiscardPolicy(Enum):
    """
    Policy of discarding data when the queue cache in sensor is full
    """
    #
    DISCARDING_OLD_DATA = bounded_queue.ThreadSafeBoundedQueue
    STOPPING_ADDING = bounded_queue.ThreadSafeBoundedQueueNoOverflow

    def __init__(self, queue_class: Type[bounded_queue.BaseThreadSafeBoundedQueue]):
        self.queue_class = queue_class
