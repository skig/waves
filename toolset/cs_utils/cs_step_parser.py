import logging
from . import cs_step

logger = logging.getLogger(__name__)


def parse_cs_steps(hex_data: str) -> list[cs_step.CSStep]:
    """Parse stream of CS steps, returning all at once.

    Args:
        hex_data: Hexadecimal string representation of data stream

    Returns:
        List of all CSStep objects parsed from stream

    Raises:
        ValueError: If data is malformed or contains invalid mode
    """
    HEADER_SIZE = 3  # mode (1) + channel (1) + data_len (1)

    data = bytes.fromhex(hex_data)
    steps = []
    offset = 0

    while offset < len(data):
        if offset + HEADER_SIZE > len(data):
            logger.error(f"Incomplete step header at offset {offset}")
            break

        mode_value = data[offset]
        channel = data[offset + 1]
        data_len = data[offset + 2]

        if mode_value > 3:
            logger.error(f"Invalid mode {mode_value} at offset {offset}, skipping step")
            offset += HEADER_SIZE + data_len
            continue

        if channel > 78:
            logger.error(f"Invalid channel {channel} at offset {offset}, skipping step")
            offset += HEADER_SIZE + data_len
            continue

        mode = cs_step.CSMode(mode_value)

        if offset + HEADER_SIZE + data_len > len(data):
            logger.error(f"Incomplete step data at offset {offset}")
            break

        step_data = data[offset + HEADER_SIZE : offset + HEADER_SIZE + data_len]
        step = parse_cs_step_from_bytes(step_data, mode, channel)
        if step is not None:
            steps.append(step)
        offset += HEADER_SIZE + data_len

    return steps


def parse_cs_step_from_bytes(data: bytes, mode: cs_step.CSMode, channel: int) -> cs_step.CSStep:
    """Parse single CS step data based on mode.

    Args:
        data: Raw binary data to parse
        mode: CS mode indicating packet structure
        channel: Channel number for this step

    Returns:
        Parsed CSStep object (mode-specific subclass)

    Raises:
        ValueError: If mode is invalid or data is malformed
    """
    if mode == cs_step.CSMode.MODE_0:
        return parse_mode0(data, channel)
    elif mode == cs_step.CSMode.MODE_1:
        return parse_mode1(data, channel)
    elif mode == cs_step.CSMode.MODE_2:
        return parse_mode2(data, channel)
    elif mode == cs_step.CSMode.MODE_3:
        return parse_mode3(data, channel)
    else:
        logger.error(f"Unknown CS mode: {mode}")
        return None


def parse_mode0(data: bytes, channel: int) -> cs_step.CSStepMode0:
    """Parse Mode 0 CS step data.

    Args:
        data: Raw binary data
        channel: Channel number

    Returns:
        Parsed CSStepMode0 object
    """
    if len(data) not in (3, 5):
        logger.error(f"Invalid Mode 0 data length: {len(data)}, expected 3 or 5")
        return None

    packet_quality = cs_step.PacketQuality(data[0])
    packet_rssi = None if data[1] == cs_step.RSSI_NOT_AVAILABLE else int.from_bytes(data[1:2], byteorder='big', signed=True)
    packet_antenna = data[2]

    measured_freq_offset = None
    if len(data) == 5:
        # Parse 2-byte 15-bit signed integer in units of 0.01 ppm
        offset_raw = int.from_bytes(data[3:5], byteorder='little', signed=True)
        measured_freq_offset = float(offset_raw)

    return cs_step.CSStepMode0(
        mode=cs_step.CSMode.MODE_0,
        channel=channel,
        packet_quality=packet_quality,
        packet_rssi=packet_rssi,
        packet_antenna=packet_antenna,
        measured_freq_offset=measured_freq_offset
    )


def parse_mode1(data: bytes, channel: int) -> cs_step.CSStepMode1:
    """Parse Mode 1 CS step data.

    Args:
        data: Raw binary data
        channel: Channel number

    Returns:
        Parsed CSStepMode1 object with raw_data field
    """
    pass


def parse_mode2(data: bytes, channel: int) -> cs_step.CSStepMode2:
    """Parse Mode 2 CS step data.

    Args:
        data: Raw binary data
        channel: Channel number

    Returns:
        Parsed CSStepMode2 object with tone data
    """
    def _sign_extend_12bit(value: int) -> int:
        """Convert 12-bit unsigned to signed integer."""
        return value - 0x1000 if value >= 0x800 else value


    # data_len = 1 (antenna) + k * 4 (where k is number of tones)
    # k can be 2, 3, 4, or 5
    if len(data) < 1 or (len(data) - 1) % 4 != 0:
        logger.error(f"Invalid Mode 2 data length: {len(data)}")
        return None

    k = (len(data) - 1) // 4
    if k not in (2, 3, 4, 5):
        logger.error(f"Invalid number of tones in Mode 2: {k}, expected 2-5")
        return None

    antenna_permutation_index = data[0]
    tones = []

    offset = 1
    for i in range(k):
        tone_pct_bytes = data[offset:offset + 3]
        bits = int.from_bytes(tone_pct_bytes, byteorder='little')
        pct_i = _sign_extend_12bit(bits & 0xFFF)
        pct_q = _sign_extend_12bit((bits >> 12) & 0xFFF)

        # Parse Tone_Quality_Indicator (1 byte)
        quality_byte = data[offset + 3]
        quality = cs_step.ToneQualityIndicator(quality_byte & 0x0F)  # 4 LSB
        quality_extension_slot = cs_step.ToneQualityIndicatorExtensionSlot((quality_byte >> 4) & 0x0F)  # 4 MSB

        tones.append(cs_step.ToneData(
            pct_i=pct_i,
            pct_q=pct_q,
            quality=quality,
            quality_extension_slot=quality_extension_slot
        ))

        offset += 4

    return cs_step.CSStepMode2(
        mode=cs_step.CSMode.MODE_2,
        channel=channel,
        antenna_permutation_index=antenna_permutation_index,
        tones=tones
    )


def parse_mode3(data: bytes, channel: int) -> cs_step.CSStepMode3:
    """Parse Mode 3 CS step data.

    Args:
        data: Raw binary data
        channel: Channel number

    Returns:
        Parsed CSStepMode3 object with raw_data field
    """
    pass
