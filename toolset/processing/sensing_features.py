"""Shared feature extraction utilities for BLE CS sensing and gesture recognition."""

from typing import Dict, Optional

import numpy as np

from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.cs_utils.cs_step import CSStepMode2, ToneQualityIndicator, ToneQualityIndicatorExtensionSlot

# Fixed BLE CS channel set used for feature vector alignment (channels 2–78, excluding advertising channels 0/1/37/38/39)
PHASE_CHANNELS = [ch for ch in range(2, 79) if ch not in (37, 38, 39)]
N_PHASE = len(PHASE_CHANNELS)
CHANNEL_INDEX = {ch: i for i, ch in enumerate(PHASE_CHANNELS)}


def sensing_drop_reason(
    initiator: Optional[SubeventResults],
    reflector: Optional[SubeventResults],
    phase_data: Optional[Dict[int, float]],
    amplitude_response: Optional[Dict[int, float]],
) -> Optional[str]:
    """Return a human-readable drop reason, or None if the sample is acceptable."""
    if initiator is None:
        return 'initiator subevent is None'
    if reflector is None:
        return 'reflector subevent is None'
    if not phase_data:
        return 'no phase slope data'
    if not amplitude_response:
        return 'no amplitude response data'

    bad_ini = first_bad_tone(initiator)
    if bad_ini:
        return f'initiator {bad_ini}'
    bad_ref = first_bad_tone(reflector)
    if bad_ref:
        return f'reflector {bad_ref}'

    emission_ini = ext_slot_emission(initiator)
    if emission_ini:
        return f'initiator {emission_ini}'
    emission_ref = ext_slot_emission(reflector)
    if emission_ref:
        return f'reflector {emission_ref}'

    return None


def ext_slot_emission(subevent: SubeventResults, threshold: float = 30.0) -> Optional[str]:
    """Return description if any TONE_EXTENSION_NOT_EXPECTED slot has magnitude above threshold.

    A large magnitude in an extension slot indicates external RF emission on that channel.
    """
    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue
        for tone in step.tones:
            if tone.quality_extension_slot != ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED:
                continue
            mag = (tone.pct_i ** 2 + tone.pct_q ** 2) ** 0.5
            if mag > threshold:
                return f'ext slot emission on ch {step.channel}: mag={mag:.1f}'
    return None


def first_bad_tone(subevent: SubeventResults) -> Optional[str]:
    """Return description when at least 1 bad tone is found, or None."""
    bad = []
    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue
        for tone in step.tones:
            if tone.quality_extension_slot == ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED:
                continue
            if tone.quality in (ToneQualityIndicator.TONE_QUALITY_MEDIUM,
                                ToneQualityIndicator.TONE_QUALITY_LOW):
                bad.append(f'ch {step.channel}={tone.quality.name}')
                if len(bad) >= 1:
                    return f'{len(bad)} bad tones: {", ".join(bad)}'
    return None


def subevent_quality_ok(subevent: Optional[SubeventResults]) -> bool:
    """Return False if any mode-2 step has a MEDIUM or LOW tone quality."""
    if subevent is None:
        return False
    for step in subevent.steps:
        if not isinstance(step, CSStepMode2):
            continue
        for tone in step.tones:
            if tone.quality in (ToneQualityIndicator.TONE_QUALITY_MEDIUM,
                                ToneQualityIndicator.TONE_QUALITY_LOW):
                return False
    return True


def build_feature_vector(
    phase_data: Optional[Dict[int, float]],
    amplitude_response: Optional[Dict[int, float]],
    use_phase: bool = True,
    use_amplitude_response: bool = True,
) -> Optional[np.ndarray]:
    """Build a fixed-length feature vector from per-channel dicts.

    Layout: [phase_ch2..ch78 (excl. adv), amplitude_response_ch2..ch78]
    Missing channels are filled with 0. Sections can be disabled via use_* flags.
    """
    if not phase_data and not amplitude_response:
        return None

    vec = np.zeros(2 * N_PHASE, dtype=np.float32)

    if phase_data and use_phase:
        channels = list(phase_data.keys())
        offset = phase_data[channels[0]]
        for ch in channels:
            idx = CHANNEL_INDEX.get(ch)
            if idx is not None:
                vec[idx] = phase_data[ch] - offset

    if amplitude_response and use_amplitude_response:
        values = list(amplitude_response.values())
        offset = min(values)
        for ch, val in amplitude_response.items():
            idx = CHANNEL_INDEX.get(ch)
            if idx is not None:
                vec[N_PHASE + idx] = val - offset

    return vec
