import argparse
from cs_data_processor import CSDataProcessor

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

    processor = CSDataProcessor()

    if args.uart:
        print("Mode: Reading from COM-ports")
        # TODO: Implement UART mode
    else:
        print("Mode: Reading from log files")
        initiator_subevents = processor.process_file(args.initiator)
        reflector_subevents = processor.process_file(args.reflector)
        print(f"Loaded {len(initiator_subevents)} initiator subevents")
        print(f"Loaded {len(reflector_subevents)} reflector subevents")


if __name__ == '__main__':
    main()
