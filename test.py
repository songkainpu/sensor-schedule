import simpy

def process_1(env):
    yield env.timeout(1)  # 等待1个时间单位
    print(f'Process 1 executed at {env.now}')

def process_2(env):
    yield env.timeout(2)  # 等待2个时间单位
    print(f'Process 2 executed at {env.now}')

env = simpy.Environment()
env.process(process_1(env))  # 添加第一个进程
env.process(process_2(env))  # 添加第二个进程

env.run()  # 运行仿真
