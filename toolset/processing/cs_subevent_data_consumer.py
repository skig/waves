

from queue import Queue
from typing import Dict, Tuple, Optional, Callable
from toolset.cs_utils.cs_subevent import SubeventResults
import time

def dual_stream_consumer(initiator_queue: Queue, reflector_queue: Queue, gui_callback: Optional[Callable] = None):
    """
    Consume subevents from initiator and reflector queues and couple them by procedure_counter.

    Args:
        initiator_queue: Queue containing initiator SubeventResults
        reflector_queue: Queue containing reflector SubeventResults
        gui_callback: Optional callback to update GUI with coupled data
    """
    initiator_buffer: Dict[int, SubeventResults] = {}
    reflector_buffer: Dict[int, SubeventResults] = {}

    initiator_done = False
    reflector_done = False

    while not (initiator_done and reflector_done):
        # Read from initiator queue
        if not initiator_done:
            initiator_data = initiator_queue.get()
            if initiator_data is None:
                initiator_done = True
            else:
                proc_counter = initiator_data.procedure_counter
                # TODO: fix issue when proc_counter wraps around
                initiator_buffer[proc_counter] = initiator_data

                # Check if we have a matching reflector
                if proc_counter in reflector_buffer:
                    process_coupled_subevents(
                        initiator_buffer.pop(proc_counter),
                        reflector_buffer.pop(proc_counter),
                        gui_callback
                    )

        # Read from reflector queue
        if not reflector_done:
            reflector_data = reflector_queue.get()
            if reflector_data is None:
                reflector_done = True
            else:
                proc_counter = reflector_data.procedure_counter
                reflector_buffer[proc_counter] = reflector_data

                # Check if we have a matching initiator
                if proc_counter in initiator_buffer:
                    process_coupled_subevents(
                        initiator_buffer.pop(proc_counter),
                        reflector_buffer.pop(proc_counter),
                        gui_callback
                    )

    # Process any remaining unpaired subevents
    print("\n=== Summary ===")
    print(f"Unpaired initiator subevents: {len(initiator_buffer)}")
    print(f"Unpaired reflector subevents: {len(reflector_buffer)}")

    if initiator_buffer:
        print(f"  Initiator procedure counters: {sorted(initiator_buffer.keys())}")
    if reflector_buffer:
        print(f"  Reflector procedure counters: {sorted(reflector_buffer.keys())}")


def process_coupled_subevents(initiator: SubeventResults, reflector: SubeventResults, gui_callback: Optional[Callable] = None):
    """Process coupled subevents and optionally update GUI.

    Args:
        initiator: Initiator subevent
        reflector: Reflector subevent
        gui_callback: Optional callback to update GUI
    """
    # Print to console
    print(f"Proc {initiator.procedure_counter}: Ini={len(initiator.steps)} steps, Ref={len(reflector.steps)} steps")

    # just for testing, TODO: remove it
    time.sleep(1)
    # Update GUI if callback provided
    if gui_callback:
        gui_callback(initiator, reflector)