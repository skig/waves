from cmath import exp
from math import cos, pi, sin
from typing import Dict, List

from toolset.cs_utils.cs_step import CSStepMode2, ToneQualityIndicatorExtensionSlot
from toolset.cs_utils.cs_subevent import SubeventResults


def calculate_channel_ifft_data(initiator: SubeventResults, reflector: SubeventResults) -> Dict[int, float]:
    """Compute iFFT magnitude of channel response built from initiator*reflector I/Q per channel."""
    channel_response = _extract_channel_response(initiator, reflector)
    if not channel_response:
        return {}

    ifft_values = _ifft(channel_response)

    return {index: abs(value) for index, value in enumerate(ifft_values)}


def calculate_music_spectrum_data(
    initiator: SubeventResults,
    reflector: SubeventResults,
    channel_spacing_hz: float = 1_000_000.0,
    spectrum_points: int = 256,
) -> Dict[int, float]:
    """Compute a single-source MUSIC delay spectrum from channel response."""
    channel_response = _extract_channel_response(initiator, reflector)
    sample_count = len(channel_response)
    if sample_count < 3:
        return {}

    subarray_length = max(2, sample_count // 2)
    covariance = _build_smoothed_covariance(channel_response, subarray_length)
    principal_eigenvector = _principal_eigenvector(covariance)
    if not principal_eigenvector:
        return {}

    spectrum: Dict[int, float] = {}
    max_delay_s = 1.0 / channel_spacing_hz
    max_value = 0.0

    for bin_index in range(spectrum_points):
        delay_s = (bin_index / spectrum_points) * max_delay_s
        steering = [exp(complex(0.0, -2.0 * pi * channel_spacing_hz * m * delay_s)) for m in range(subarray_length)]

        projection = sum(principal_eigenvector[m].conjugate() * steering[m] for m in range(subarray_length))
        denominator = max(subarray_length - abs(projection) ** 2, 1e-12)
        value = 1.0 / denominator
        spectrum[bin_index] = value
        if value > max_value:
            max_value = value

    if max_value <= 0.0:
        return spectrum

    return {bin_index: value / max_value for bin_index, value in spectrum.items()}


def _extract_channel_response(initiator: SubeventResults, reflector: SubeventResults) -> List[complex]:
    initiator_iq = _extract_channel_average_iq(initiator)
    reflector_iq = _extract_channel_average_iq(reflector)

    common_channels = sorted(set(initiator_iq.keys()) & set(reflector_iq.keys()))
    if not common_channels:
        return []

    return [initiator_iq[channel] * reflector_iq[channel] for channel in common_channels]


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


def _build_smoothed_covariance(response: List[complex], subarray_length: int) -> List[List[complex]]:
    snapshots = len(response) - subarray_length + 1
    covariance = [[0j for _ in range(subarray_length)] for _ in range(subarray_length)]

    for start in range(snapshots):
        subarray = response[start:start + subarray_length]
        for row in range(subarray_length):
            row_value = subarray[row]
            for col in range(subarray_length):
                covariance[row][col] += row_value * subarray[col].conjugate()

    scale = 1.0 / snapshots
    for row in range(subarray_length):
        for col in range(subarray_length):
            covariance[row][col] *= scale

    return covariance


def _principal_eigenvector(matrix: List[List[complex]], max_iterations: int = 40) -> List[complex]:
    dimension = len(matrix)
    if dimension == 0:
        return []

    vector = [0j for _ in range(dimension)]
    vector[0] = 1.0 + 0.0j

    for _ in range(max_iterations):
        next_vector = []
        for row in range(dimension):
            value = sum(matrix[row][col] * vector[col] for col in range(dimension))
            next_vector.append(value)

        norm = sum(abs(value) ** 2 for value in next_vector) ** 0.5
        if norm <= 1e-15:
            return []

        vector = [value / norm for value in next_vector]

    return vector