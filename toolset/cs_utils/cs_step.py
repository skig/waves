from enum import IntEnum
from dataclasses import dataclass
from typing import Optional

from math import atan2, sqrt

# Special value of Packet_RSSI field
RSSI_NOT_AVAILABLE = 0x7F


class CSMode(IntEnum):
    MODE_0 = 0x00
    MODE_1 = 0x01
    MODE_2 = 0x02
    MODE_3 = 0x03

class PacketQuality(IntEnum):
    AA_SUCCESS = 0x00
    AA_BIT_ERRORS = 0x01
    AA_NOT_FOUND = 0x02

class PacketNADM(IntEnum):
    ATTACK_IS_EXTREMELY_UNLIKELY = 0x00
    ATTACK_IS_VERY_UNLIKELY = 0x01
    ATTACK_IS_UNLIKELY = 0x02
    ATTACK_IS_POSSIBLE = 0x03
    ATTACK_IS_LIKELY = 0x04
    ATTACK_IS_VERY_LIKELY = 0x05
    ATTACK_IS_EXTREMELY_LIKELY = 0x06
    UNKNOWN_NADM = 0xFF

class ToneQualityIndicator(IntEnum):
    TONE_QUALITY_HIGH = 0x00
    TONE_QUALITY_MEDIUM = 0x01
    TONE_QUALITY_LOW = 0x02
    TONE_QUALITY_UNAVAILABLE = 0x03

    def short_description(self) -> str:
        if self == ToneQualityIndicator.TONE_QUALITY_HIGH:
            return "High"
        if self == ToneQualityIndicator.TONE_QUALITY_MEDIUM:
            return "Medium"
        if self == ToneQualityIndicator.TONE_QUALITY_LOW:
            return "Low"
        return "Not available"

class ToneQualityIndicatorExtensionSlot(IntEnum):
    NOT_TONE_EXTENSION_SLOT = 0x00
    TONE_EXTENSION_NOT_EXPECTED = 0x01
    TONE_EXTENSION_EXPECTED = 0x02


@dataclass
class ToneData:
    pct_i: int # in signed int 12-bit format
    pct_q: int # in signed int 12-bit format
    quality: ToneQualityIndicator
    quality_extension_slot: ToneQualityIndicatorExtensionSlot

    def __str__(self):
        if self.quality_extension_slot != ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED:
            return f"Tone (I:{self.pct_i} Q:{self.pct_q} Mag: {sqrt(self.pct_i ** 2 + self.pct_q ** 2):.2f}, Phase: {atan2(self.pct_q, self.pct_i):.2f}, Quality: {self.quality.short_description()})"
        else:
            return f"Empty extension slot (Mag: {sqrt(self.pct_i ** 2 + self.pct_q ** 2):.2f})"

    __repr__ = __str__


@dataclass
class CSStep:
    mode: CSMode
    channel: int

    def __str__(self):
        return f"Step(mode:{self.mode.name} ch:{self.channel})"

    __repr__ = __str__


@dataclass
class CSStepMode0(CSStep):
    packet_quality: PacketQuality
    packet_rssi: Optional[int]  # in dBm, None if not available (0x7F)
    packet_antenna: int
    measured_freq_offset: Optional[float] = None # in 0.01 ppm. Only available on Initiator

    def __str__(self):
        rssi_str = f"{self.packet_rssi}dBm" if self.packet_rssi is not None else "N/A"
        return f"Mode0 (ch:{self.channel:02d} rssi:{rssi_str} qual:{self.packet_quality.name})"

    def __repr__(self):
        return f"\n{self.__str__()}"


@dataclass
class CSStepMode1(CSStep):
    raw_data: bytes
    # TODO: add mode-1 specific fields

    def __str__(self):
        return f"Mode1 (ch:{self.channel:02d})"

    __repr__ = __str__

@dataclass
class CSStepMode2(CSStep):
    antenna_permutation_index: int
    tones: list[ToneData]

    def __str__(self):
        return f"Mode2 (ch:{self.channel:02d} tones:{self.tones})"

    def __repr__(self):
        return f"\n{self.__str__()}"

@dataclass
class CSStepMode3(CSStep):
    raw_data: bytes
    # TODO: add mode-3 specific fields

    def __str__(self):
        return f"Mode3 (ch:{self.channel:02d})"

    __repr__ = __str__
