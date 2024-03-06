import threading
import queue
import time


class FairLock:
    def __init__(self):
        self.queue = queue.Queue()
        self.current_lock = None

    def acquire(self):
        lock = threading.Lock()
        self.queue.put(lock)
        while True:
            if lock == self.queue.queue[0] and (self.current_lock is None or not self.current_lock.locked()):
                self.current_lock = lock
                lock.acquire()
                break
            else:
                time.sleep(0.01)  # Prevent tight loop, introduce slight delay

    def release(self):
        self.current_lock.release()
        self.queue.get()

    # Context manager methods
    def __enter__(self):
        self.acquire()
        return self  # 返回实例本身，如果需要的话

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
