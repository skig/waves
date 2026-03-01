from math import cos, pi, sin

from toolset.cs_utils import cs_step, cs_subevent
from toolset.processing.cs_channel_ifft import calculate_channel_ifft_data, calculate_music_spectrum_data


def _build_subevent_with_mode2_steps(procedure_counter: int, mode2_steps: list[cs_step.CSStepMode2]) -> cs_subevent.SubeventResults:
    return cs_subevent.SubeventResults(
        procedure_counter=procedure_counter,
        reference_power_level=-16,
        procedure_done_status=cs_subevent.ProcedureDoneStatus.PROC_ALL_RESULTS_COMPLETED,
        subevent_done_status=cs_subevent.SubeventDoneStatus.SUBEVENT_ALL_RESULTS_COMPLETED,
        procedure_abort_reason=cs_subevent.ProcedureAbortReason.PROC_NO_ABORT,
        subevent_abort_reason=cs_subevent.SubeventAbortReason.SUBEVENT_NO_ABORT,
        num_steps_reported=len(mode2_steps),
        steps=mode2_steps,
    )


def _mode2_step(channel: int, i_value: int, q_value: int) -> cs_step.CSStepMode2:
    return cs_step.CSStepMode2(
        mode=cs_step.CSMode.MODE_2,
        channel=channel,
        antenna_permutation_index=0,
        tones=[
            cs_step.ToneData(
                pct_i=i_value,
                pct_q=q_value,
                quality=cs_step.ToneQualityIndicator.TONE_QUALITY_HIGH,
                quality_extension_slot=cs_step.ToneQualityIndicatorExtensionSlot.NOT_TONE_EXTENSION_SLOT,
            )
        ],
    )


class TestChannelIfft:
    def test_ifft_from_product_of_initiator_and_reflector_iq(self):
        initiator = _build_subevent_with_mode2_steps(
            procedure_counter=1,
            mode2_steps=[
                _mode2_step(channel=1, i_value=1, q_value=0),
                _mode2_step(channel=2, i_value=1, q_value=0),
            ],
        )
        reflector = _build_subevent_with_mode2_steps(
            procedure_counter=1,
            mode2_steps=[
                _mode2_step(channel=1, i_value=1, q_value=0),
                _mode2_step(channel=2, i_value=-1, q_value=0),
            ],
        )

        ifft_data = calculate_channel_ifft_data(initiator, reflector)

        assert len(ifft_data) == 2
        assert ifft_data[0] == 0.0
        assert ifft_data[1] == 1.0

    def test_returns_empty_dict_when_no_common_channels(self):
        initiator = _build_subevent_with_mode2_steps(
            procedure_counter=2,
            mode2_steps=[_mode2_step(channel=1, i_value=10, q_value=1)],
        )
        reflector = _build_subevent_with_mode2_steps(
            procedure_counter=2,
            mode2_steps=[_mode2_step(channel=5, i_value=4, q_value=-2)],
        )

        ifft_data = calculate_channel_ifft_data(initiator, reflector)

        assert ifft_data == {}


class TestMusicSpectrum:
    def test_music_peak_matches_expected_delay(self):
        channel_count = 16
        channel_spacing_hz = 1_000_000.0
        target_delay_us = 0.25
        target_delay_s = target_delay_us * 1e-6
        amplitude = 1000

        initiator_steps = []
        reflector_steps = []

        for channel in range(channel_count):
            phase = -2.0 * pi * channel * channel_spacing_hz * target_delay_s
            i_value = int(round(amplitude * cos(phase)))
            q_value = int(round(amplitude * sin(phase)))
            initiator_steps.append(_mode2_step(channel=channel, i_value=i_value, q_value=q_value))
            reflector_steps.append(_mode2_step(channel=channel, i_value=1, q_value=0))

        initiator = _build_subevent_with_mode2_steps(procedure_counter=3, mode2_steps=initiator_steps)
        reflector = _build_subevent_with_mode2_steps(procedure_counter=3, mode2_steps=reflector_steps)

        spectrum = calculate_music_spectrum_data(initiator, reflector, channel_spacing_hz=channel_spacing_hz, spectrum_points=256)

        assert spectrum
        assert abs(max(spectrum.values()) - 1.0) < 1e-9

        peak_bin = max(spectrum, key=spectrum.get)
        peak_delay_us = (peak_bin / 256) * (1.0 / channel_spacing_hz) * 1e6
        assert abs(peak_delay_us - target_delay_us) < 0.03