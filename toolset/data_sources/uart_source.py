from typing import Iterator, Optional
import serial
from toolset.data_sources.base import DataSource
from toolset.cs_utils.cs_subevent_parser import parse_cs_subevent_result
from toolset.cs_utils.cs_subevent import SubeventResults


class UartDataSource(DataSource):
    START_MARKER = "I: CS Subevent result received:"
    END_MARKER = "I: CS Subevent end"

    def __init__(self, port: str, baudrate: int = 115200, log_file: Optional[str] = None):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.buffer = ""
        self.log_file = log_file
        self.log_handle = None

        if self.log_file:
            self.log_handle = open(self.log_file, 'w', encoding='utf-8')

    def read(self) -> Iterator[Optional[SubeventResults]]:
        """Yield subevents from UART as they arrive."""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )

            while True:
                if self.serial_conn.in_waiting > 0:
                    chunk = self.serial_conn.read(self.serial_conn.in_waiting)
                    try:
                        decoded_chunk = chunk.decode('utf-8', errors='replace')
                        self.buffer += decoded_chunk

                        # Write raw data to log file if enabled
                        if self.log_handle:
                            self.log_handle.write(decoded_chunk)
                            self.log_handle.flush()
                    except UnicodeDecodeError:
                        continue

                    # Process complete subevents in buffer
                    while self.START_MARKER in self.buffer:
                        start_idx = self.buffer.find(self.START_MARKER)

                        # Discard any data before the start marker
                        if start_idx > 0:
                            self.buffer = self.buffer[start_idx:]
                            start_idx = 0

                        end_idx = self.buffer.find(self.END_MARKER, start_idx + len(self.START_MARKER))

                        if end_idx != -1:
                            # Extract complete subevent from start to end marker
                            subevent_text = self.buffer[start_idx:end_idx + len(self.END_MARKER)]
                            self.buffer = self.buffer[end_idx + len(self.END_MARKER):]

                            parsed = parse_cs_subevent_result(subevent_text)
                            if parsed:
                                yield parsed
                        else:
                            # Don't have complete subevent yet, wait for more data
                            break

        except serial.SerialException as e:
            print(f"Serial error on {self.port}: {e}")
        except KeyboardInterrupt:
            pass

    def close(self):
        """Close serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        if self.log_handle:
            self.log_handle.close()
