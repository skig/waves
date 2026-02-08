from typing import Iterator, Optional
from toolset.data_sources.base import DataSource
from toolset.cs_data_processor import CSDataProcessor
from toolset.cs_utils.cs_subevent import SubeventResults


class FileDataSource(DataSource):
    """Reads CS data from log file."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.processor = CSDataProcessor()
        self._data = None
        self._index = 0

    def read(self) -> Iterator[Optional[SubeventResults]]:
        """Yield subevents from file."""
        if self._data is None:
            self._data = self.processor.process_file(self.filepath)

        for subevent in self._data:
            yield subevent

    def close(self):
        """No resources to clean up for file source."""
        pass
