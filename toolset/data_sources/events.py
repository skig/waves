from dataclasses import dataclass
from toolset.cs_utils.cs_subevent import SubeventResults


class CSEvent:
    """Base class for all events emitted by data sources."""
    pass


@dataclass
class StatusEvent(CSEvent):
    """A CS setup status transition (e.g. connection, encryption)."""
    key: str


@dataclass
class CapabilitiesEvent(CSEvent):
    """CS capabilities text block received after capability exchange."""
    text: str


@dataclass
class SubeventResultEvent(CSEvent):
    """A parsed CS subevent result."""
    subevent: SubeventResults


@dataclass
class ProcedureParamsEvent(CSEvent):
    """Connection interval and procedure interval parsed from initiator UART output."""
    connection_interval_ms: int
    procedure_interval: int
