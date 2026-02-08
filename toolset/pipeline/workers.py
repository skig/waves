from queue import Queue
from threading import Event
from toolset.data_sources.base import DataSource


def producer_worker(source: DataSource, output_queue: Queue, stop_event: Event):
    """
    Read from source and push to queue.

    Args:
        source: DataSource instance
        output_queue: Queue to push data to
        stop_event: Event to signal stop
    """
    try:
        for data in source.read():
            if stop_event.is_set():
                break
            output_queue.put(data)
    finally:
        output_queue.put(None)  # Sentinel
        source.close()
