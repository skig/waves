from typing import Dict
from math import log, sqrt
from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.cs_utils.cs_step import CSStepMode2, ToneQualityIndicatorExtensionSlot


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

def _extract_channel_rssi(subevent: SubeventResults) -> Dict[int, float]:
    channel_rssi = {}

    rpl_dbm = subevent.reference_power_level

    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue

        if not step.tones:
            continue

        avg_i, avg_q = _calculate_average_rssi(step)
        mag = sqrt(avg_i ** 2 + avg_q ** 2)
        rssi_dbm = 20 * log(abs(mag / 2048), 10) + rpl_dbm
        # TODO: if channel_rssi is not empty, we need to do something smart. Maybe find average or something like that?
        channel_rssi[step.channel] = rssi_dbm

    return channel_rssi

def calculate_rssi_data(initiator: SubeventResults, reflector: SubeventResults) -> Dict[int, float]:
    initiator_rssi_vals = _extract_channel_rssi(initiator)
    reflector_rssi_vals = _extract_channel_rssi(reflector)

    return initiator_rssi_vals, reflector_rssi_vals
