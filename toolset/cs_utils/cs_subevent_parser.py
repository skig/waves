import logging
import re
from typing import Optional
from . import cs_step_parser
from . import cs_subevent

logger = logging.getLogger(__name__)


def parse_cs_subevent_result(text_data: str) -> Optional[cs_subevent.SubeventResults]:
    """Parse CS subevent result from text log format.

    Expected format:
        I: CS Subevent result received:
        I:  - Procedure counter: 0
        I:  - Procedure done status: 0
        I:  - Subevent done status: 0
        I:  - Procedure abort reason: 0
        I:  - Subevent abort reason: 0
        I:  - Reference power level: -16
        I:  - Num antenna paths: 1
        I:  - Num steps reported: 75
        I:  - Step data buffer length: 888 bytes
        I: Raw step data:
          <hex data lines>

    Args:
        text_data: Text log data containing subevent result

    Returns:
        SubeventResults object or None if parsing fails
    """
    try:
        # Extract procedure counter
        match = re.search(r'Procedure counter:\s*(\d+)', text_data)
        if not match:
            logger.error("Could not find Procedure counter in text data")
            return None
        procedure_counter = int(match.group(1))

        # Extract procedure done status
        match = re.search(r'Procedure done status:\s*(\d+)', text_data)
        if not match:
            logger.error("Could not find Procedure done status in text data")
            return None
        procedure_done_status = cs_subevent.ProcedureDoneStatus(int(match.group(1)))

        # Extract subevent done status
        match = re.search(r'Subevent done status:\s*(\d+)', text_data)
        if not match:
            logger.error("Could not find Subevent done status in text data")
            return None
        subevent_done_status = cs_subevent.SubeventDoneStatus(int(match.group(1)))

        # Extract procedure abort reason
        match = re.search(r'Procedure abort reason:\s*(\d+)', text_data)
        if not match:
            logger.error("Could not find Procedure abort reason in text data")
            return None
        procedure_abort_reason = cs_subevent.ProcedureAbortReason(int(match.group(1)))

        # Extract subevent abort reason
        match = re.search(r'Subevent abort reason:\s*(\d+)', text_data)
        if not match:
            logger.error("Could not find Subevent abort reason in text data")
            return None
        subevent_abort_reason = cs_subevent.SubeventAbortReason(int(match.group(1)))

        # Extract reference power level
        match = re.search(r'Reference power level:\s*(-?\d+)', text_data)
        if not match:
            logger.error("Could not find Reference power level in text data")
            return None
        reference_power_level = int(match.group(1))

        # Extract num steps reported
        match = re.search(r'Num steps reported:\s*(\d+)', text_data)
        if not match:
            logger.error("Could not find Num steps reported in text data")
            return None
        num_steps_reported = int(match.group(1))

        # Extract measured frequency offset (optional, Initiator only)
        measured_freq_offset = None
        match = re.search(r'Measured frequency offset:\s*(-?\d+(?:\.\d+)?)', text_data)
        if match:
            measured_freq_offset = float(match.group(1))

        # Extract raw step data (hex string)
        # Find "Raw step data:" and collect all hex data after it, but stop before end marker
        match = re.search(r'Raw step data:(.+?)(?:\n\n|I: CS Subevent end|\Z)', text_data, re.DOTALL)
        if not match:
            if num_steps_reported > 0:
                logger.error("Could not find Raw step data in text data")
            return None

        # Extract hex data, removing comments, whitespace, and non-hex characters
        hex_section = match.group(1)
        hex_data = re.sub(r'[^0-9a-fA-F]', '', hex_section)

        # Parse steps using cs_step_parser
        steps = cs_step_parser.parse_cs_steps(hex_data)

        return cs_subevent.SubeventResults(
            procedure_counter=procedure_counter,
            measured_freq_offset=measured_freq_offset,
            reference_power_level=reference_power_level,
            procedure_done_status=procedure_done_status,
            subevent_done_status=subevent_done_status,
            procedure_abort_reason=procedure_abort_reason,
            subevent_abort_reason=subevent_abort_reason,
            num_steps_reported=num_steps_reported,
            steps=steps
        )

    except (ValueError, KeyError) as e:
        logger.error(f"Error parsing text data: {e}")
        return None
