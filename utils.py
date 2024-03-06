import os
import subprocess
from functools import wraps


def singleton_factory(cls):
    instance = {}

    def get_instance(*args, **kwargs):
        if cls not in instance:
            instance[cls] = cls(*args, **kwargs)
        return instance[cls]

    return get_instance


def synchronized(lock):
    """装饰器：在函数执行前后加锁和解锁"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)

        return wrapper

    return decorator


# 指定你的图片所在的目录
# images_directory = './images'

# 构建ffmpeg命令
ffmpeg_command = [
    'ffmpeg',
    '-framerate', '24',
    '-pattern_type', 'glob',
    '-i', '*.png',
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    'out.mp4'
]


def compositing_video_through_ffmpeg(images_directory):
    subprocess.run(ffmpeg_command, cwd=images_directory)


def init_env(images_directory):
    ensure_directory_exists(images_directory)
    if os.path.exists(images_directory) and os.path.isdir(images_directory):
        # 列出目录中的所有文件和子目录
        for filename in os.listdir(images_directory):
            file_path = os.path.join(images_directory, filename)
            # 检查是否是文件（跳过目录）
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Deleted: {file_path}")
            # 如果还需要删除目录，请在这里添加额外的逻辑
        print("Directory cleared.")
    else:
        print("The specified path does not exist or is not a directory.")


def ensure_directory_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Directory {path} created.")
    else:
        print(f"Directory {path} already exists.")
