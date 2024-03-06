import bounded_queue
from enum import Enum
from typing import Union, Tuple, Type

ERROR_RATE = 0.05

class SensorEnum(Enum):
    # 16.436个异常中断  平均每秒产生的
    # 共占用575.26ms
    # 根据阻塞队列 每个设备 局部内存区满的时间都是1s
    # 经测试 52个 信号 pb数据 大小为 219byte 1个数据信号的pb数据为14byte
    # ACCELEROMETER 是 1S 每次频率 必须取 执行 80.25ms
    #
    # 52 Protobuf Size: 219 byte
    # 1 Protobuf Size: 14 byte
    # 40 size: 171 8.75ms
    # 25 size: 110 6.84375ms
    # 默认设置 http2  frame headerheader
    # 256 kbps = 256 /8 = 32 x 10^3 bytw
    # 传输时间 最多 (100+9+219) /  （32 x 10^3) = 10.25 ms
    # 传输时间最少 4.96875

    # 发送一个数据包的总时间: 10.25 + 50 -> 最多60.25ms
    # 总得拉数据+ 发送数据包总时间 最多为  80.25ms
    # 40 size: 171 78.75ms
    # 25 size: 110 76.84375ms
    # 最少 4.96875
    # 共计 391.0625ms
    # 481.5
    # miniCycle is 1
    # Major cycle is 2 second
    #
    # range unit mg
    ACCELEROMETER = (52, 0.05, (-2, 2), -1.9, 1.9, 52, 80.25, "mg")
    # range unit dps
    GYROSCOPE = (52, 0.05, (-60, 60), -50, 50, 52, 80.25, "dps")
    # range unit rH%
    HUMIDITY = (1, 0.05, (30, 70), 40, 60, 2, 74.96875, "rH%")
    # range unit Celsius
    TEMPERATURE = (1, 0.05, (15, 30), 20, 25, 2, 74.96875, "Celsius")
    # range unit Gauss
    MAGNETOMETER = (40, 0.05, (0, 100), 5, 95, 40, 78.75, "Gauss")
    # range unit hPa
    PRESSURE = (25, 0.05, (0, 100000), 5, 99995, 25, 76.84375, "hPa")

    def __init__(self, rate: float, error: float, range_tuple: Tuple[float, float],
                 mini_threshold: Union[int, float], max_threshold: Union[int, float], data_capacity: int,
                 expected_cost: float, unit:str):
        """
        :param rate: unitL Hz
        :param error:  unit 1
        :param range_tuple: it depends on the enum
        :param mini_threshold
        :param max_threshold
        :param data_capacity unit ms
        :param expected_cost:
        :param unit:
        """
        self.rate = rate
        self.error = error
        self.range_tuple = range_tuple
        self.mini_threshold = mini_threshold
        self.max_threshold = max_threshold
        self.data_capacity = data_capacity
        self.expected_cost = expected_cost
        self.unit = unit

class DiscardPolicy(Enum):
    """
    Policy of discarding data when the queue cache in sensor is full
    """
    #
    DISCARDING_OLD_DATA = bounded_queue.ThreadSafeBoundedQueue
    STOPPING_ADDING = bounded_queue.ThreadSafeBoundedQueueNoOverflow

    def __init__(self, queue_class: Type[bounded_queue.BaseThreadSafeBoundedQueue]):
        self.queue_class = queue_class
