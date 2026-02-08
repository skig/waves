from typing import Iterator, Optional
import serial
from toolset.data_sources.base import DataSource
from toolset.cs_utils.cs_subevent_parser import parse_cs_subevent_result
from toolset.cs_utils.cs_subevent import SubeventResults


class UartDataSource(DataSource):
    MARKER = "I: CS Subevent result received:"

    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.buffer = ""

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
                        self.buffer += chunk.decode('utf-8', errors='replace')
                    except UnicodeDecodeError:
                        continue

                    while self.MARKER in self.buffer:
                        start_idx = self.buffer.find(self.MARKER)
                        next_idx = self.buffer.find(self.MARKER, start_idx + len(self.MARKER))

                        if next_idx != -1:
                            subevent_text = self.buffer[start_idx:next_idx]
                            self.buffer = self.buffer[next_idx:]

                            parsed = parse_cs_subevent_result(subevent_text)
                            if parsed:
                                yield parsed
                        else:
                            break

        except serial.SerialException as e:
            print(f"Serial error on {self.port}: {e}")
        except KeyboardInterrupt:
            pass

    def close(self):
        """Close serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
