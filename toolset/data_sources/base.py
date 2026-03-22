from abc import ABC, abstractmethod
from typing import Iterator
from toolset.data_sources.events import CSEvent

_STATUS_MARKERS = {
    'connection': 'Connected to',
    'encryption': 'Security changed',
    'cs_security': 'CS security enabled',
    'cs_capabilities': 'CS capability exchange completed',
    'cs_config': 'CS config creation complete',
    'cs_procedure': ('CS procedures started', 'CS procedures configured'),
}


class DataSource(ABC):
    """Abstract base class for all data sources."""

    @abstractmethod
    def read(self) -> Iterator[CSEvent]:
        """
        Yields CSEvent objects as they become available.
        Events can be StatusEvent, CapabilitiesEvent, or SubeventResultEvent.
        """
        pass

    @abstractmethod
    def close(self):
        """Clean up resources."""
        pass
