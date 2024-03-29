from collections import deque
from typing import List
from fair_lock import FairLock



class BaseThreadSafeBoundedQueue:
    """
    Base class for a thread-safe bounded queue.
    """

    def __init__(self, capacity):
        self.capacity = capacity
        self.active_queue = deque(maxlen=capacity)
        self.back_up_queue = deque(maxlen=capacity)
        self.lock = FairLock()
        self.get_clear_lock = FairLock()
        self.is_over_flow:bool = False

    def put(self, item):
        raise NotImplementedError("Must be implemented by subclass.")

    def get_and_clear_all(self) -> deque:
        raise NotImplementedError("Must be implemented by subclass.")

    def get_copy_no_clear_all(self) -> List:
        with self.get_clear_lock:
            return list(self.active_queue)


class ThreadSafeBoundedQueue(BaseThreadSafeBoundedQueue):
    """
    Thread-safe bounded queue which removes the oldest element when full.
    """

    def put(self, item):
        with self.lock:
            if len(self.active_queue) == self.capacity:
                self.is_over_flow = True
                self.active_queue.popleft()
            else:
                self.is_over_flow = False
            self.active_queue.append(item)

    def get_and_clear_all(self) -> deque:
        with self.get_clear_lock:
            with self.lock:
                self.back_up_queue, self.active_queue = self.active_queue, self.back_up_queue
            back_up = self.back_up_queue
            self.back_up_queue = deque(maxlen=self.capacity)
            return back_up


class ThreadSafeBoundedQueueNoOverflow(BaseThreadSafeBoundedQueue):
    """
    Thread-safe bounded queue that does not add new items if the queue is full.
    """

    def put(self, item):
        with self.lock:
            if len(self.active_queue) < self.capacity:
                self.active_queue.append(item)
                self.is_over_flow = False
            else:
                self.is_over_flow = True

            # If the queue is full, do nothing.

    def get_and_clear_all(self) -> deque:
        with self.get_clear_lock:
            with self.lock:
                self.back_up_queue, self.active_queue = self.active_queue, self.back_up_queue
            back_up = self.back_up_queue
            self.back_up_queue = deque(maxlen=self.capacity)
            return back_up
