from typing import Dict
from math import log, sqrt
from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.cs_utils.cs_step import CSStepMode2, ToneQualityIndicatorExtensionSlot

def avg_dbm(a, b):
    a_mw = 10 ** (a / 10)
    b_mw = 10 ** (b / 10)
    avg_mw = (a_mw + b_mw) / 2
    return 10 * log(avg_mw, 10)

def calculate_amplitude_response(initiator_rssi_vals, reflector_rssi_vals):
    tx_power_dbm = 0 # hardcode TX power to 0 dBm for simplicity, even though it can be different depending on CS configuration
    amplitude_response = {}
    for channel in initiator_rssi_vals:
        initiator_dbm = initiator_rssi_vals[channel]
        reflector_dbm = initiator_dbm
        if channel in reflector_rssi_vals:
            reflector_dbm = reflector_rssi_vals[channel]
        amplitude_response[channel] = avg_dbm(initiator_dbm, reflector_dbm) - tx_power_dbm
    return amplitude_response

def calculate_amplitude_response_data(initiator: SubeventResults, reflector: SubeventResults) -> Dict[int, float]:
    initiator_rssi_vals = _extract_channel_rssi(initiator)
    reflector_rssi_vals = _extract_channel_rssi(reflector)

    return calculate_amplitude_response(initiator_rssi_vals, reflector_rssi_vals)

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
        # can fail here if mag = 0 in case of subevent aborted on one device only, need to fix
        # use log/20260406_115854_initiator.txt log/20260406_115854_reflector.txt files to reproduce
        rssi_dbm = 20 * log(abs(mag / 2048), 10) + rpl_dbm
        # TODO: if channel_rssi is not empty, we need to do something smart. Maybe find average or something like that?
        channel_rssi[step.channel] = rssi_dbm

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
