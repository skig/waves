from abc import ABC, abstractmethod
from typing import Optional, Iterator
from toolset.cs_utils.cs_subevent import SubeventResults


class DataSource(ABC):
    """Abstract base class for all data sources."""

    @abstractmethod
    def read(self) -> Iterator[Optional[SubeventResults]]:
        """
        Yields SubeventResults as they become available.
        Returns None when done/disconnected.
        """
        pass

    @abstractmethod
    def close(self):
        """Clean up resources."""
        pass
