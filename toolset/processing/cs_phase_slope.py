from typing import Dict
from math import atan2
from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.cs_utils.cs_step import CSStepMode2, ToneQualityIndicatorExtensionSlot


def calculate_phase_slope_data(initiator: SubeventResults, reflector: SubeventResults) -> Dict[int, float]:
    initiator_phases = _extract_channel_phases(initiator)
    reflector_phases = _extract_channel_phases(reflector)

    common_channels = set(initiator_phases.keys()) & set(reflector_phases.keys())

    phase_sums = {}
    for channel in common_channels:
        phase_sums[channel] = initiator_phases[channel] + reflector_phases[channel]

    return phase_sums


def _extract_channel_phases(subevent: SubeventResults) -> Dict[int, float]:
    channel_phases = {}

    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue

        if not step.tones:
            continue

        avg_i, avg_q = _calculate_average_iq(step)
        phase = atan2(avg_q, avg_i)

        channel_phases[step.channel] = phase

    return channel_phases


def _calculate_average_iq(step: CSStepMode2) -> tuple[float, float]:
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
