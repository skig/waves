from dataclasses import dataclass
from typing import Optional
from enum import IntEnum

from toolset import cs_step

class ProcedureDoneStatus(IntEnum):
    PROC_ALL_RESULTS_COMPLETED = 0x00
    PROC_PARTIAL_RESULTS_TO_FOLLOW = 0x01
    PROC_ALL_SUBSEQUENT_PROCEDURES_ABORTED = 0x0F

class SubeventDoneStatus(IntEnum):
    SUBEVENT_ALL_RESULTS_COMPLETED = 0x00
    SUBEVENT_PARTIAL_RESULTS_TO_FOLLOW = 0x01
    SUBEVENT_ALL_SUBSEQUENT_PROCEDURES_ABORTED = 0x0F

class ProcedureAbortReason(IntEnum):
    PROC_NO_ABORT = 0x00
    PROC_ABORT_LOCAL_OR_REMOTE_REQUEST = 0x01
    PROC_LESS_THAN_15_CHANNELS = 0x02
    PROC_CHMAP_UPDATE_INSTANT_PASSED = 0x03
    PROC_ABORT_UNSPECIFIED = 0x0F

class SubeventAbortReason(IntEnum):
    SUBEVENT_NO_ABORT = 0x00
    SUBEVENT_ABORT_LOCAL_OR_REMOTE_REQUEST = 0x01
    SUBEVENT_NO_CS_SYNC = 0x02
    SUBEVENT_SCHEDULING_CONFLICT_OR_LIMITED_RESOURCES = 0x03
    SUBEVENT_ABORT_UNSPECIFIED = 0x0F


@dataclass
class SubeventResults:
    procedure_counter: int
    measured_freq_offset: Optional[float] = None # in 0.01 ppm. Only available on Initiator
    reference_power_level: int
    procedure_done_status: ProcedureDoneStatus
    subevent_done_status: SubeventDoneStatus
    procedure_abort_reason: ProcedureAbortReason
    subevent_abort_reason: SubeventAbortReason
    num_steps_reported: int
    steps: list[cs_step.CSStep]
