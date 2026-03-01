from toolset.cs_utils import cs_step, cs_subevent
from toolset.processing.cs_channel_ifft import calculate_channel_ifft_data


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