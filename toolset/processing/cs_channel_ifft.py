from math import cos, pi, sin
from typing import Dict, List

from toolset.cs_utils.cs_step import CSStepMode2, ToneQualityIndicatorExtensionSlot
from toolset.cs_utils.cs_subevent import SubeventResults


def calculate_channel_ifft_data(initiator: SubeventResults, reflector: SubeventResults) -> Dict[int, float]:
    """Compute iFFT magnitude of channel response built from initiator*reflector I/Q per channel."""
    initiator_iq = _extract_channel_average_iq(initiator)
    reflector_iq = _extract_channel_average_iq(reflector)

    common_channels = sorted(set(initiator_iq.keys()) & set(reflector_iq.keys()))
    if not common_channels:
        return {}

    channel_response = [initiator_iq[channel] * reflector_iq[channel] for channel in common_channels]
    ifft_values = _ifft(channel_response)

    return {index: abs(value) for index, value in enumerate(ifft_values)}


def _extract_channel_average_iq(subevent: SubeventResults) -> Dict[int, complex]:
    channel_iq: Dict[int, complex] = {}

    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue

        valid_tones = [
            tone for tone in step.tones
            if tone.quality_extension_slot != ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED
        ]
        if not valid_tones:
            continue

        avg_i = sum(tone.pct_i for tone in valid_tones) / len(valid_tones)
        avg_q = sum(tone.pct_q for tone in valid_tones) / len(valid_tones)
        channel_iq[step.channel] = complex(avg_i, avg_q)

    return channel_iq


def _ifft(values: List[complex]) -> List[complex]:
    sample_count = len(values)
    if sample_count == 0:
        return []

    output: List[complex] = []
    for n in range(sample_count):
        acc = 0j
        for k, value in enumerate(values):
            angle = 2.0 * pi * k * n / sample_count
            twiddle = complex(cos(angle), sin(angle))
            acc += value * twiddle
        output.append(acc / sample_count)

    return output