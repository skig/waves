from typing import Dict
from math import sqrt
from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.cs_utils.cs_step import CSStepMode2, ToneQualityIndicatorExtensionSlot

def calculate_rssi_data(initiator: SubeventResults, reflector: SubeventResults) -> Dict[int, float]:
    initiator_phases = _extract_channel_rssi(initiator)
    reflector_phases = _extract_channel_rssi(reflector)

    common_channels = set(initiator_phases.keys()) & set(reflector_phases.keys())

    rssi_avg = {}
    for channel in common_channels:
        print(f"ch {channel}: {initiator_phases[channel]}, {reflector_phases[channel]}")
        rssi_avg[channel] = initiator_phases[channel]

    return rssi_avg

def _extract_channel_rssi(subevent: SubeventResults) -> Dict[int, float]:
    channel_rssi = {}

    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue

        if not step.tones:
            continue

        avg_i, avg_q = _calculate_average_rssi(step)
        rssi = sqrt(avg_i ** 2 + avg_q ** 2)

        channel_rssi[step.channel] = rssi

    return channel_rssi


def _calculate_average_rssi(step: CSStepMode2) -> tuple[float, float]:
    valid_tones = [
        tone for tone in step.tones
        if tone.quality_extension_slot != ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED
    ]

    if not valid_tones:
        return 0.0, 0.0

    sum_i = sum(tone.pct_i for tone in valid_tones)
    sum_q = sum(tone.pct_q for tone in valid_tones)

    count = len(valid_tones)
    return sum_i / count, sum_q / count
