import argparse
from queue import Queue
from threading import Thread, Event

from toolset.data_sources import FileDataSource
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
        help='Path to initiator log file or COM-port (e.g., /dev/ttyUSB0 or COM3)'
    )

    parser.add_argument(
        '-r', '--reflector',
        required=True,
        help='Path to reflector log file or COM-port (e.g., /dev/ttyUSB1 or COM4)'
    )

    parser.add_argument(
        '--uart',
        action='store_true',
        help='If specified, treat initiator and reflector as COM-ports instead of log files'
    )

    args = parser.parse_args()

    # Create separate queues for each stream
    initiator_queue = Queue(maxsize=100)
    reflector_queue = Queue(maxsize=100)
    stop_event = Event()

    if args.uart:
        print("Mode: Reading from COM-ports")
        # TODO: Implement UART mode
        print("UART mode not yet implemented")
        return
    else:
        print("Mode: Reading from log files")

        # Create data sources
        initiator_source = FileDataSource(args.initiator)
        reflector_source = FileDataSource(args.reflector)

        # Create producer threads
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

        # Create consumer thread
        consumer = Thread(
            target=dual_stream_consumer,
            args=(initiator_queue, reflector_queue),
            name="Consumer"
        )

        # Start all threads
        print("Starting data processing pipeline...")
        initiator_producer.start()
        reflector_producer.start()
        consumer.start()

        # Wait for completion
        try:
            initiator_producer.join()
            reflector_producer.join()
            consumer.join()
            print("\nProcessing complete!")
        except KeyboardInterrupt:
            print("\nStopping...")
            stop_event.set()
            initiator_producer.join()
            reflector_producer.join()
            consumer.join()


if __name__ == '__main__':
    main()
