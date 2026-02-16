#!/usr/bin/env python3

import argparse
import os
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

    args = parser.parse_args()

    # Validate arguments
    if args.log_uart and not args.uart:
        parser.error("--log-uart can only be used with --uart")

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
        initiator_log_file = os.path.join(log_dir, f'initiator_{timestamp}.txt')
        reflector_log_file = os.path.join(log_dir, f'reflector_{timestamp}.txt')
        print(f"Raw logging enabled:")
        print(f"  Initiator: {initiator_log_file}")
        print(f"  Reflector: {reflector_log_file}")

    if args.uart:
        print("Mode: Reading from COM-ports")
        initiator_source = UartDataSource(args.initiator, baudrate=115200, log_file=initiator_log_file)
        reflector_source = UartDataSource(args.reflector, baudrate=115200, log_file=reflector_log_file)

    else:
        print("Mode: Reading from log files")
        initiator_source = FileDataSource(args.initiator)
        reflector_source = FileDataSource(args.reflector)

    initiator_producer = Thread(
        target=producer_worker,
        args=(initiator_source, initiator_queue, stop_event),
        name="InitiatorProducer"
    )

    reflector_producer = Thread(
        target=producer_worker,
        args=(reflector_source, reflector_queue, stop_event),
        name="ReflectorProducer"
    )

    viewer = launch_viewer()

    consumer = Thread(
        target=dual_stream_consumer,
        args=(initiator_queue, reflector_queue, viewer.update_live_data),
        name="Consumer"
    )

    print("Starting data processing pipeline...")
    initiator_producer.start()
    reflector_producer.start()
    consumer.start()

    try:
        viewer.run()
    except KeyboardInterrupt:
        print("\nStopping...")

    stop_event.set()
    initiator_producer.join(timeout=1)
    reflector_producer.join(timeout=1)
    consumer.join(timeout=1)
    print("\nProcessing complete!")


if __name__ == '__main__':
    main()
