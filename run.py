#!/usr/bin/env python3

import argparse
import os
import signal
import time
from datetime import datetime
from queue import Queue
from threading import Thread, Event

from toolset.data_sources import FileDataSource
from toolset.data_sources.uart_source import UartDataSource
from toolset.pipeline import producer_worker
from toolset.processing.cs_subevent_data_consumer import dual_stream_consumer
from toolset.gui.cs_viewer import launch_viewer


def main():
    parser = argparse.ArgumentParser(
        description='Process Bluetooth Channel sounding PBR data'
    )

    parser.add_argument(
        '-i', '--initiator',
        required=True,
        help='Path to initiator log file or COM-port (e.g., /dev/ttyACM1)'
    )

    parser.add_argument(
        '-r', '--reflector',
        required=True,
        help='Path to reflector log file or COM-port (e.g., /dev/ttyACM3)'
    )

    parser.add_argument(
        '--uart',
        action='store_true',
        help='If specified, treat initiator and reflector as COM-ports instead of log files'
    )

    parser.add_argument(
        '--log-uart',
        action='store_true',
        help='Write raw UART data to log files in log/ folder'
    )

    parser.add_argument(
        '--ml',
        action='store_true',
        help='Enable the Sensing tab for ML-based features'
    )

    parser.add_argument(
        '--ml-handler',
        metavar='SCRIPT',
        default=None,
        help='Path to a Python script invoked during live ML recognition (requires --ml)'
    )

    theme_group = parser.add_mutually_exclusive_group()
    theme_group.add_argument(
        '--dark',
        dest='dark_mode',
        action='store_true',
        default=True,
        help='Use dark theme (default)'
    )
    theme_group.add_argument(
        '--light',
        dest='dark_mode',
        action='store_false',
        help='Use light theme'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.log_uart and not args.uart:
        parser.error("--log-uart can only be used with --uart")
    if args.ml and not args.uart:
        parser.error("--ml requires --uart")
    if args.ml_handler and not args.ml:
        parser.error("--ml-handler requires --ml")

    # Create separate queues for each stream
    initiator_queue = Queue(maxsize=100)
    reflector_queue = Queue(maxsize=100)
    stop_event = Event()

    # Setup raw logging if requested
    initiator_log_file = None
    reflector_log_file = None
    if args.log_uart:
        log_dir = 'log'
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        initiator_log_file = os.path.join(log_dir, f'{timestamp}_initiator.txt')
        reflector_log_file = os.path.join(log_dir, f'{timestamp}_reflector.txt')
        print(f"Raw logging enabled:")
        print(f"  Initiator: {initiator_log_file}")
        print(f"  Reflector: {reflector_log_file}")

    if args.uart:
        print("Mode: Reading from COM-ports")
        initiator_source = UartDataSource(args.initiator, baudrate=1000000)
        reflector_source = UartDataSource(args.reflector, baudrate=1000000)

        initiator_source.set_stop_event(stop_event)
        reflector_source.set_stop_event(stop_event)

        initiator_source.open()
        reflector_source.open()

        print("Sending reboot command to initiator and reflector...")
        initiator_source.send(b'r')
        reflector_source.send(b'r')
        time.sleep(1)

        initiator_source.flush_input()
        reflector_source.flush_input()
        print("Buffers flushed.")

        initiator_source.enable_logging(initiator_log_file)
        reflector_source.enable_logging(reflector_log_file)

        print("Sending start command to initiator...")
        initiator_source.send(b's')

    else:
        print("Mode: Reading from log files")
        initiator_source = FileDataSource(args.initiator)
        reflector_source = FileDataSource(args.reflector)

    def shutdown():
        """Signal all threads to stop and close open data sources."""
        stop_event.set()
        initiator_source.close()
        reflector_source.close()

    viewer = launch_viewer(dark_mode=args.dark_mode, ml=args.ml, ml_handler=args.ml_handler, on_close=shutdown)

    def _sigint_handler(sig, frame):
        shutdown()
        viewer.root.quit()

    signal.signal(signal.SIGINT, _sigint_handler)

    initiator_producer = Thread(
        target=producer_worker,
        args=(initiator_source, initiator_queue, stop_event),
        kwargs={
            'status_callback': viewer.update_connection_status,
            'capabilities_callback': viewer.update_capabilities_text,
            'procedure_params_callback': viewer.update_procedure_params,
        },
        name="InitiatorProducer",
        daemon=True,
    )

    reflector_producer = Thread(
        target=producer_worker,
        args=(reflector_source, reflector_queue, stop_event),
        name="ReflectorProducer",
        daemon=True,
    )

    consumer = Thread(
        target=dual_stream_consumer,
        args=(initiator_queue, reflector_queue, viewer.update_live_data),
        name="Consumer",
        daemon=True,
    )

    print("Starting data processing pipeline...")
    initiator_producer.start()
    reflector_producer.start()
    consumer.start()

    viewer.run()

    shutdown()
    print("\nProcessing complete!")


if __name__ == '__main__':
    main()
