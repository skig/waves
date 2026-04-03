import re
from typing import Iterator
from toolset.data_sources.base import DataSource, _STATUS_MARKERS
from toolset.data_sources.events import CSEvent, StatusEvent, CapabilitiesEvent, SubeventResultEvent
from toolset.cs_utils.cs_subevent_parser import parse_cs_subevent_result


class FileDataSource(DataSource):
    """Reads CS data from log file."""

    def __init__(self, filepath: str):
        self.filepath = filepath

    def read(self) -> Iterator[CSEvent]:
        """Yield events from file."""
        with open(self.filepath) as f:
            raw_text = f.read()

        yield from _parse_log_lines(raw_text)

        for subevent in _parse_subevents(raw_text):
            if subevent is not None:
                yield SubeventResultEvent(subevent)

    def close(self):
        pass


def _parse_log_lines(text: str) -> Iterator[CSEvent]:
    """Scan log text for status markers and capabilities."""
    collecting_capabilities = False
    capabilities_lines: list[str] = []

    for line in text.splitlines():
        for key, marker in _STATUS_MARKERS.items():
            markers = marker if isinstance(marker, tuple) else (marker,)
            if any(m in line for m in markers):
                yield StatusEvent(key)

        if collecting_capabilities:
            if 'I:  - ' in line:
                capabilities_lines.append(line.split('I:  - ', 1)[1])
            else:
                if capabilities_lines:
                    yield CapabilitiesEvent('\n'.join(capabilities_lines))
                collecting_capabilities = False
                capabilities_lines = []

        if _STATUS_MARKERS['cs_capabilities'] in line:
            collecting_capabilities = True
            capabilities_lines = []

    if capabilities_lines:
        yield CapabilitiesEvent('\n'.join(capabilities_lines))


def _parse_subevents(text: str):
    """Extract CS Subevent blocks from log text and parse them."""
    pattern = r'(?=I: CS Subevent result received:)'
    blocks = re.split(pattern, text)

    for block in blocks:
        if not block.strip() or 'CS Subevent result received:' not in block:
            continue

        next_marker = block.find('I: CS Subevent result received:', 1)
        subevent_text = block[:next_marker] if next_marker != -1 else block

        yield parse_cs_subevent_result(subevent_text)
