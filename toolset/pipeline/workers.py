from queue import Queue
from threading import Event
from typing import Optional, Callable
from toolset.data_sources.base import DataSource
from toolset.data_sources.events import CSEvent, StatusEvent, CapabilitiesEvent, SubeventResultEvent


def producer_worker(
    source: DataSource,
    output_queue: Queue,
    stop_event: Event,
    status_callback: Optional[Callable[[str], None]] = None,
    capabilities_callback: Optional[Callable[[str], None]] = None,
):
    """
    Read events from source, dispatch status/capabilities immediately,
    and push SubeventResultEvents to the queue.

    Args:
        source: DataSource instance
        output_queue: Queue to push subevent data to
        stop_event: Event to signal stop
        status_callback: Optional callback for status events
        capabilities_callback: Optional callback for capabilities events
    """
    try:
        for event in source.read():
            if stop_event.is_set():
                break
            if isinstance(event, StatusEvent):
                if status_callback:
                    status_callback(event.key)
            elif isinstance(event, CapabilitiesEvent):
                if capabilities_callback:
                    capabilities_callback(event.text)
            elif isinstance(event, SubeventResultEvent):
                output_queue.put(event.subevent)
    finally:
        output_queue.put(None)  # Sentinel
        source.close()
