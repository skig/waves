from typing import Iterator, Optional
import serial
from toolset.data_sources.base import DataSource, _STATUS_MARKERS
from toolset.data_sources.events import CSEvent, StatusEvent, CapabilitiesEvent, SubeventResultEvent
from toolset.cs_utils.cs_subevent_parser import parse_cs_subevent_result


class UartDataSource(DataSource):
    START_MARKER = "I: CS Subevent result received:"
    END_MARKER = "I: CS Subevent end"

    def __init__(self, port: str, baudrate: int = 1000000):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.buffer = ""
        self.log_handle = None
        self._line_buffer = ""
        self._collecting_capabilities = False
        self._capabilities_lines: list[str] = []

    def enable_logging(self, log_file: Optional[str]):
        """Start logging raw UART data to a file."""
        if log_file:
            self.log_handle = open(log_file, 'w', encoding='utf-8')

    def open(self):
        """Open the serial connection."""
        if self.serial_conn is None or not self.serial_conn.is_open:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )

    def send(self, data: bytes):
        """Send data over the serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write(data)

    def flush_input(self):
        """Discard all data in the input buffer."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.reset_input_buffer()
        self.buffer = ""

    def _process_line(self, line: str) -> Iterator[CSEvent]:
        """Check a line for status markers and capabilities data."""
        for key, marker in _STATUS_MARKERS.items():
            markers = marker if isinstance(marker, tuple) else (marker,)
            if any(m in line for m in markers):
                yield StatusEvent(key)

        if self._collecting_capabilities:
            if 'I:  - ' in line:
                self._capabilities_lines.append(line.split('I:  - ', 1)[1])
            else:
                if self._capabilities_lines:
                    yield CapabilitiesEvent('\n'.join(self._capabilities_lines))
                self._collecting_capabilities = False
                self._capabilities_lines = []

        if _STATUS_MARKERS['cs_capabilities'] in line:
            self._collecting_capabilities = True
            self._capabilities_lines = []

    def read(self) -> Iterator[CSEvent]:
        """Yield events from UART as they arrive."""
        try:
            self.open()

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

                        # Check for status markers line-by-line
                        self._line_buffer += decoded_chunk
                        while '\n' in self._line_buffer:
                            line, self._line_buffer = self._line_buffer.split('\n', 1)
                            yield from self._process_line(line.rstrip('\r'))
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
                                yield SubeventResultEvent(parsed)
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
