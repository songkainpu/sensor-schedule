import simpy
import random

from bounded_queue import BaseThreadSafeBoundedQueue
from typing import Tuple, Generator, Union

from my_enum import SensorEnum, DiscardPolicy



class Sensor:
    def __init__(self, env: simpy.Environment, sensor_enum: SensorEnum,
                 discard_strategy: DiscardPolicy = DiscardPolicy.DISCARDING_OLD_DATA,
                 capability: int = 10):
        self.env = env
        self.sensor_enum: SensorEnum = sensor_enum
        self.discard_strategy: DiscardPolicy = discard_strategy
        self.capability: int = capability
        # depends on discard_strategy
        self.queue: BaseThreadSafeBoundedQueue = discard_strategy.value()
        self.interval = 1 / self.sensor_enum.rate

    def generate_data(self):
        while True:
            self.queue.put(item=self.generate_random_datum())
            yield self.env.timeout(delay=self.interval)

    def generate_random_datum(self) -> float:
        bottom, top = self.sensor_enum.range_tuple
        data: float = random.uniform(a=bottom, b=top)
        error: float = random.uniform(a=-0.05, b=0.05)
        data *= (1+error)
        data = max(bottom, min(data, top))
        return data





def sensor_data_generator(env: simpy.Environment, sensor: SensorEnum) -> Generator[simpy.Event, None, None]:
    while True:
        # Generate data with random error
        if sensor.range_tuple[0] is not None and sensor.range_tuple[1] is not None:
            data = random.uniform(*sensor.range_tuple) * (1 + random.uniform(-sensor.error, sensor.error))
        else:
            raise Exception("Data range not defined")
        print(f"{env.now}: {sensor.name} data: {data}")
        # Simulate polling time variability
        # TIPS: use uniform distribution to ensure the average time is 15ms
        # polling_time = random.uniform(10, 20) / 1000  # Convert milliseconds to seconds
        # yield env.timeout(polling_time)


def main():
    env = simpy.Environment()
    for sensor in SensorEnum:
        env.process(sensor_data_generator(env, sensor))
    env.run(until=10)  # Simulate for 10 seconds


if __name__ == "__main__":
    main()
