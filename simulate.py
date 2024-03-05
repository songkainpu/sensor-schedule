import time
import typing

import simpy
import random

from simpy import Resource

from message_pb2 import Message
from bounded_queue import BaseThreadSafeBoundedQueue, ThreadSafeBoundedQueue
from typing import Tuple, Generator, Union, List, Dict, Optional, Iterable
from my_enum import SensorEnum, DiscardPolicy
from utils import singleton_factory
import functools

# 单位 byte
HTTP2_FRAME_HEADER_SIZE = 9
# 单位buye
HTTP2_HEADER_SIZE = 100
# 256 kbs = 256/8 k·Byte·s
BANDWIDTH: float = 256 / 8
# the first line is the first minor cycle
# the second is the second minor cycle
# minor cycle is 1 second
SCHEDULE_ORDER: List[SensorEnum] = \
    ([SensorEnum.ACCELEROMETER, SensorEnum.GYROSCOPE, SensorEnum.MAGNETOMETER, SensorEnum.PRESSURE, SensorEnum.HUMIDITY]
     + [SensorEnum.ACCELEROMETER, SensorEnum.GYROSCOPE, SensorEnum.MAGNETOMETER, SensorEnum.PRESSURE,
        SensorEnum.TEMPERATURE])

NO_SENSOR_SPIN_INTERVAL_SECONDS: float = .1

STM32_CONTROLLER_RESOURCE: Optional[Resource] = None

ENV: Optional[simpy.Environment] = None


def print_queue(func):
    """A decorator that prints the queue after the function call."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)  # Call the original function/method
        time = ENV.now
        method_name = func.__name__  # 获取当前执行的方法名
        # print(f"Method Name: {method_name}")  # 打印方法名
        if not (isinstance(result,float) or isinstance(result, int)):
            print(f"type of result:{type(result)}")
        # print("Current Queue:", self.queue.active_queue)  # Print the queue
        return result

    return wrapper


class Sensor:
    def __init__(self, env: simpy.Environment, sensor_enum: SensorEnum,
                 discard_strategy: DiscardPolicy = DiscardPolicy.DISCARDING_OLD_DATA,
                 capability: int = 10):
        self.env = env
        self.sensor_enum: SensorEnum = sensor_enum
        self.discard_strategy: DiscardPolicy = discard_strategy
        self.capability: int = capability
        # depends on discard_strategy
        self.queue: BaseThreadSafeBoundedQueue = discard_strategy.value(self.capability)
        self.interval = 1 / self.sensor_enum.rate

    def generate_data(self):
        while True:
            self.queue.put(item=self._generate_random_datum())
            yield self.env.timeout(delay=self.interval)
    @print_queue
    def _generate_random_datum(self) -> float:
        bottom, top = self.sensor_enum.range_tuple
        data: float = random.uniform(a=bottom, b=top)
        error: float = random.uniform(a=-0.05, b=0.05)
        data *= (1 + error)
        data = max(bottom, min(data, top))
        return data

    @print_queue
    def poll_data(self) -> List[float]:
        dequeue = self.queue.get_and_clear_all()
        if dequeue is None or len(dequeue) == 0:
            return []
        return list(dequeue)


# key please refer to my_enum.SensorEnum
SENSOR_DICT: Dict[str, Sensor] = {}


# def sensor_data_generator(env: simpy.Environment, sensor: SensorEnum) -> Generator[simpy.Event, None, None]:
#     while True:
#         # Generate data with random error
#         if sensor.range_tuple[0] is not None and sensor.range_tuple[1] is not None:
#             data = random.uniform(*sensor.range_tuple) * (1 + random.uniform(-sensor.error, sensor.error))
#         else:
#             raise Exception("Data range not defined")
#         print(f"{env.now}: {sensor.name} data: {data}")
#         # Simulate polling time variability
# TIPS: use uniform distribution to ensure the average time is 15ms
# polling_time = random.uniform(10, 20) / 1000  # Convert milliseconds to seconds
# yield env.timeout(polling_time)

def _generate_random_data_transmit_delay() -> float:
    """
    Generate random delay time for transmitting data
    unit is second
    :return: unit is second
    """
    return random.uniform(0.02, 0.05)


def _mock_data_transmit(sensor_enum: SensorEnum, data: Iterable[float], cur_time: Union[float, int]) -> float:
    random_delay: float = _generate_random_data_transmit_delay()
    my_message = Message()
    my_message.sensor_name = sensor_enum.name
    my_message.time = cur_time
    my_message.data_array.extend(data)  # 添加到data_array字段
    serialized_data = my_message.SerializeToString()
    protobuf_size = len(serialized_data)
    transmit_time = (protobuf_size + HTTP2_HEADER_SIZE + HTTP2_HEADER_SIZE) / BANDWIDTH
    total_transmit_time: float = transmit_time + random_delay
    print(f"total_transmit_time:{total_transmit_time}")
    return total_transmit_time / 1000


def _generate_random_polling_time() -> float:
    """
    Generates random time for polling
    unit is second
    :return:  unit is second
    """
    return random.uniform(0.01, 0.02)


def _check_data_transmit(sensor_enum: SensorEnum, data: Iterable[float], cur_time: Union[float, int]) -> float:
    top = sensor_enum.max_threshold
    bottom = sensor_enum.mini_threshold
    if any(value < bottom or value > top for value in data):
        print(f"trigger the urgent event sensor:{sensor_enum}, time:{cur_time}")
        return 0.035
    return 0


def stm32_controller_process(env: simpy.Environment) -> Generator[simpy.Event, None, None]:
    total_len: int = len(SCHEDULE_ORDER)
    idx = 0
    while True:
        sensor_type: SensorEnum = SCHEDULE_ORDER[idx]
        sensor: Sensor = SENSOR_DICT[sensor_type.name]
        if sensor is None:
            time.sleep(0.1)
            continue
        idx += 1
        idx %= total_len
        # poll_data
        with STM32_CONTROLLER_RESOURCE.request() as req:
            yield req
            data_list: List[float] = sensor.poll_data()
            polling_time: float = _generate_random_polling_time()
            print(f"polling time: {polling_time}")
            yield env.timeout(polling_time)
            # check data
            yield env.timeout(_check_data_transmit(sensor_enum=sensor_type, data=data_list, cur_time=env.now))
            # transmit data
            total_transmit_time = _mock_data_transmit(sensor_enum=sensor_type, data=data_list, cur_time=env.now)
            yield env.timeout(total_transmit_time)


def main():
    env = simpy.Environment()
    global ENV
    ENV = env
    simpy.Resource(env=env, capacity=1)
    global STM32_CONTROLLER_RESOURCE
    STM32_CONTROLLER_RESOURCE = singleton_factory(simpy.Resource)(**{
        "env": env,
        "capacity": 1
    })
    for sensor_enum in SensorEnum:
        tem_sensor: Sensor = Sensor(env=env, sensor_enum=sensor_enum,
                                    discard_strategy=DiscardPolicy.DISCARDING_OLD_DATA)
        SENSOR_DICT[sensor_enum.name] = tem_sensor
        env.process(tem_sensor.generate_data())
    env.process(stm32_controller_process(env=env))
    env.run(until=20)  # Simulate for 10 seconds


def test():
    my_queue: typing.List[float] = [float(i) for i in range(25)]
    my_message = Message()
    my_message.sensor_name = "test"
    my_message.time = 99
    my_message.data_array.extend(my_queue)  # 添加到data_array字段
    serialized_data = my_message.SerializeToString()
    protobuf_size = len(serialized_data)
    print("52 Protobuf Size:", protobuf_size, "byte")
    my_queue: typing.List[float] = [1, 2]
    my_message2 = Message()
    my_message2.sensor_name = "test"
    my_message2.time = 99
    my_message2.data_array.extend(my_queue)  # 添加到data_array字段
    serialized_data = my_message2.SerializeToString()
    protobuf_size = len(serialized_data)
    print("1 Protobuf Size:", protobuf_size, "byte")
    # env = simpy.Environment()
    # for sensor in SensorEnum:
    #     env.process(sensor_data_generator(env, sensor))
    # env.run(until=10)  # Simulate for 10 seconds


if __name__ == "__main__":
    main()
