import time
import functools
import random
import time
import typing
from datetime import datetime
from typing import Generator, Union, List, Dict, Optional, Iterable

import matplotlib.pyplot as plt
import simpy
from simpy import Resource

from bounded_queue import BaseThreadSafeBoundedQueue
from fair_lock import FairLock
from message_pb2 import Message
from my_enum import SensorEnum, DiscardPolicy, thread_local, EventEnum
from utils import singleton_factory, compositing_video_through_ffmpeg, init_env
from init_mysql import save_event ,final_save_event
# 单位 byte
HTTP2_FRAME_HEADER_SIZE = 9
# 单位buye
HTTP2_HEADER_SIZE = 100
# 256 kbs = 256/8 k·Byte·s
BANDWIDTH: float = 256 / 8
# the first line is the first minor cycle
# Each substring is the tasks that should be finished in a minor cycle
SCHEDULE_ORDER: List[List[SensorEnum]] = [
    [SensorEnum.ACCELEROMETER, SensorEnum.GYROSCOPE, SensorEnum.MAGNETOMETER, SensorEnum.PRESSURE, SensorEnum.HUMIDITY],
    [SensorEnum.ACCELEROMETER, SensorEnum.GYROSCOPE, SensorEnum.MAGNETOMETER, SensorEnum.PRESSURE,
     SensorEnum.TEMPERATURE]
]

NO_SENSOR_SPIN_INTERVAL_SECONDS: float = .1

STM32_CONTROLLER_RESOURCE: Optional[Resource] = None

ENV: Optional[simpy.Environment] = None

GLOBAL_CURRENT_SENSOR_DATA: Dict[str, Iterable[float]] = {

}
IMAGE_RANGE = [SensorEnum.ACCELEROMETER,
               SensorEnum.GYROSCOPE,
               SensorEnum.HUMIDITY,
               SensorEnum.TEMPERATURE,
               SensorEnum.MAGNETOMETER,
               SensorEnum.PRESSURE]
FUNC_NAME_OP_NAME_DICT: Dict[str, str] = {
    "_generate_random_datum": "sensor generates data",
    "poll_data": "controller polls data "
}
draw_image_lock: FairLock = FairLock()
MINI_MINOR: float = 1

DISCARD_POLICY: DiscardPolicy = DiscardPolicy.DISCARDING_OLD_DATA

BATCH_ID: Optional[str] = None


def draw_image(func_name: str, env_time: Union[int, float], called_sensor: SensorEnum):
    if len(GLOBAL_CURRENT_SENSOR_DATA) != 6:
        print(f"there is not enough sensor data to draw")
        return
    fig, axs = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle(f"time:{round(env_time, 2) if isinstance(env_time, float) else env_time} "
                 f"Sensor:{called_sensor.name} | {FUNC_NAME_OP_NAME_DICT[func_name]} ", fontsize=16)
    sensor: Sensor = SENSOR_DICT[called_sensor.name]
    for index, ax in enumerate(axs.flat):
        sensor_type: SensorEnum = IMAGE_RANGE[index]
        sensor_data = GLOBAL_CURRENT_SENSOR_DATA.get(sensor_type.name, [])
        ax.set_title(f"Sensor: {sensor_type.name}")
        ax.set_ylabel(f"Unit {sensor_type.unit}")
        max_data_points = max(len(data) for data in GLOBAL_CURRENT_SENSOR_DATA.values() if data is not None)

        if sensor_data:
            ax.plot(sensor_data, marker='o', linestyle='', markersize=8)  # 绘制传感器数据
            ax.set_xticks(range(0, max_data_points))
            ax.set_xlim(-0.5, max_data_points - 0.5)
            bottom = sensor_type.mini_threshold
            top = sensor_type.max_threshold
            ax.axhline(bottom, color='red', linestyle='--')
            ax.axhline(top, color='red', linestyle='--')

            if any(value > top or value < bottom for value in sensor_data):
                ax.set_facecolor('#FFFF99')  # 将这个子图的背景设置为黄色
                ax.text(0.5, 0.9, "URGENT", transform=ax.transAxes, color='red', fontsize=12, ha='center')
            if sensor_type == called_sensor and sensor is not None and sensor.queue.is_over_flow:
                ax.set_facecolor('#FF9999')  # 如果溢出，将这个子图的背景设置为红色
                ax.text(0, 1, "Cache is Full", transform=ax.transAxes, color='red', fontsize=12, ha='left',
                        verticalalignment='top')
                print(f"Cache is Full！！！sensor:{called_sensor}")
                save_event(event=EventEnum.OVER_FLOW, simpy_time=env_time, sensor=sensor_type)

        else:
            ax.text(0.5, 0.5, "No data available", transform=ax.transAxes, ha='center', va='center')

    plt.tight_layout()
    plt.savefig(
        f'images{MINI_MINOR}-{DISCARD_POLICY.name}/{time.time()}-{called_sensor.name}-{FUNC_NAME_OP_NAME_DICT[func_name]}.png')
    plt.close(fig)


def print_queue(func):
    """A decorator that prints the queue after the function call."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)  # Call the original function/method
        simpy_time = ENV.now
        method_name = func.__name__  # 获取当前执行的方法名
        print(f"Method Name: {method_name}")  # 打印方法名
        display_result = result
        if isinstance(display_result, float) or isinstance(display_result, int):
            display_result = list(self.queue.active_queue) if len(self.queue.active_queue) != 0 else []
        sensor_type: SensorEnum = self.sensor_enum
        with draw_image_lock:
            global GLOBAL_CURRENT_SENSOR_DATA
            print(f"result:{display_result}")
            GLOBAL_CURRENT_SENSOR_DATA[sensor_type.name] = display_result
            draw_image(func_name=method_name, env_time=simpy_time, called_sensor=sensor_type)
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
        print(data)
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
    my_message.sensor_id = sensor_enum.name
    my_message.timestamp = cur_time
    my_message.sensor_data.extend(data)  # 添加到data_array字段
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
    pre_time: Optional[float] = None
    while True:
        pre_time = env.now
        sensor_type_list: List[SensorEnum] = SCHEDULE_ORDER[idx]
        for sensor_type in sensor_type_list:
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
            if env.now >= pre_time + MINI_MINOR and sensor_type != SensorEnum.HUMIDITY and sensor != SensorEnum.TEMPERATURE:
                print(f"timeout. sensor:{sensor_type}")
                save_event(event=EventEnum.TIME_OUT, simpy_time=env.now, sensor=sensor_type)
                break
        yield env.timeout(max(0.0, pre_time + MINI_MINOR - env.now))


def process_inputs():
    minor = input("please input the mini minor")
    global MINI_MINOR
    MINI_MINOR = float(minor)
    mode = input("please input data cache mode when sensor cache is full. 1 for discarding oldest datum "
                 "and 2 for stopping adding")
    mode = int(mode)
    global DISCARD_POLICY
    DISCARD_POLICY = DiscardPolicy.get_discard_policy_by_number(mode)


def main():
    process_inputs()
    global BATCH_ID
    BATCH_ID = f"{MINI_MINOR}-{DISCARD_POLICY.name}-{datetime.now()}"
    thread_local.BATCH_ID = BATCH_ID
    init_env(f'./images{MINI_MINOR}-{DISCARD_POLICY.name}')
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
                                    discard_strategy=DISCARD_POLICY,
                                    capability=sensor_enum.data_capacity)
        SENSOR_DICT[sensor_enum.name] = tem_sensor
        env.process(tem_sensor.generate_data())
    env.process(stm32_controller_process(env=env))
    env.run(until=30)
    compositing_video_through_ffmpeg(f'./images{MINI_MINOR}-{DISCARD_POLICY.name}')
    final_save_event()


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
