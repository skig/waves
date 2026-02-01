import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'toolset', 'cs_utils'))

import cs_subevent_parser
import cs_subevent


class TestParseCSSubeventResult:
    """Tests for CS subevent result parser."""

    def test_parse(self):
        """Test parsing CS subevent result from text log format."""
        text_data = """
I: CS Subevent result received:
I:  - Procedure counter: 0
I:  - Procedure done status: 0
I:  - Subevent done status: 0
I:  - Procedure abort reason: 0
I:  - Subevent abort reason: 0
I:  - Reference power level: -16
I:  - Num antenna paths: 1
I:  - Num steps reported: 75
I:  - Step data buffer length: 888 bytes
I: Raw step data:
  000b0500d301327f000f0500d301327f
 003b0500db012c7f02050900d2df0400
 ff5f0012023a09007140f6006e30f620
 020d0900d29ffb00d57ffb20024c0900
 8540f5008430f520020b090013500500
 0b700520024909009e9f0c00fcbf0012
 024709001fdffe00f85fff1202020900
 babffc00bc8ffc20023e090040bffb00
 3feffb2002140900f49ffb00fd4f0012
 02100900fd2ffb00fd4f001202200900
 a93f050000700012021b0900c1af0400
 bd6f04200245090009e0f1000430ff12
 02420900acb0f700b100f820021a0900
 d3ff0400fbbfff120226090082effc00
 810ffd2002110900e55f0400fccfff12
 020609003680fb000060001202070900
 ef8f0500ec8f052002130900ba1fff00
 fe5f00120248090096aff300fd3fff12
 02080900b3ff0200b1bf022002300900
 e07ff600f83f0012023d0900c330fd00
 0a10001202150900baef0000b9ef0020
 020f0900d0ff0300fcbfff1202350900
 5bff03000790ff1202040900e97f0500
 04300012022409007ff0fd00f9bfff12
 024b0900cbc0fa00cf50fb2002390900
 9610070093600720023409008b500600
 09300012023c0900c490fe00f88fff12
 022b090044f0070000800012020a0900
 1b4005001860052002360900740ff900
 fb9f0012023809009f0006000770ff12
 0229090080df0300f84f0012023b0900
 bf00fe00be90fd2002410900b75ff300
 f69f0012022509002410080022100820
 02440900337ffa000cf0ff12022a0900
 15d0080008000012021d0900f55ff900
 f84ff92002320900635f030061ef0220
 02120900d27ffc00d54ffc20023f0900
 c8b0fc00cc50fd200237090030f0f400
 0460ff12022f0900924ff9000160ff12
 020c0900cbcffb00ceaffb20021f0900
 d2af0600f81f0012022109001b70f800
 f81f00120228090080affc00f83f0012
 022e0900d71f0900d50f092002430900
 bf10f900c160f92002160900b8cf0000
 b8df0020024609002310f20022f0f120
 023109006110f8006750f820021e0900
 6a2002006950022002220900b2bff900
 f9cfff12020e0900d88ffb00db6ffb20
 02030900cb6f0400fb3f001202400900
 331f0300f96fff12022c0900989ff900
 9d4ff920022d09009000020090100220
 021c0900b88f0400b67f042002330900
 8f900500f98fff1202270900e39ff700
 e98ff720020909001760050014600520
 024a0900506f08000a70ff1202230900
 817ffe00807ffe20
"""
        result = cs_subevent_parser.parse_cs_subevent_result(text_data)

        assert result is not None
        assert result.procedure_counter == 0
        assert result.reference_power_level == -16
        assert result.procedure_done_status == cs_subevent.ProcedureDoneStatus.PROC_ALL_RESULTS_COMPLETED
        assert result.subevent_done_status == cs_subevent.SubeventDoneStatus.SUBEVENT_ALL_RESULTS_COMPLETED
        assert result.procedure_abort_reason == cs_subevent.ProcedureAbortReason.PROC_NO_ABORT
        assert result.subevent_abort_reason == cs_subevent.SubeventAbortReason.SUBEVENT_NO_ABORT
        assert result.num_steps_reported == 75
        assert result.measured_freq_offset is None
        assert len(result.steps) == result.num_steps_reported

    def test_parse_with_freq_offset(self):
        """Test parsing text data with measured frequency offset."""
        text_data = """
I: CS Subevent result received:
I:  - Procedure counter: 5
I:  - Measured frequency offset: 12.5
I:  - Procedure done status: 1
I:  - Subevent done status: 0
I:  - Procedure abort reason: 0
I:  - Subevent abort reason: 0
I:  - Reference power level: -20
I:  - Num antenna paths: 2
I:  - Num steps reported: 10
I:  - Step data buffer length: 120 bytes
I: Raw step data:
  000b0500d301327f
"""
        result = cs_subevent_parser.parse_cs_subevent_result(text_data)

        assert result is not None
        assert result.procedure_counter == 5
        assert result.measured_freq_offset == 12.5
        assert result.reference_power_level == -20
        assert result.procedure_done_status == cs_subevent.ProcedureDoneStatus.PROC_PARTIAL_RESULTS_TO_FOLLOW
        assert result.num_steps_reported == 10

    def test_parse_missing_field(self):
        """Test parsing text data with missing required field."""
        text_data = """
I: CS Subevent result received:
I:  - Procedure counter: 0
I:  - Reference power level: -16
I: Raw step data:
  000b0500d301327f
"""
        result = cs_subevent_parser.parse_cs_subevent_result(text_data)
        assert result is None

    def test_parse_no_step_data(self):
        """Test parsing text data without raw step data section."""
        text_data = """
I: CS Subevent result received:
I:  - Procedure counter: 0
I:  - Procedure done status: 0
I:  - Subevent done status: 0
I:  - Procedure abort reason: 0
I:  - Subevent abort reason: 0
I:  - Reference power level: -16
I:  - Num antenna paths: 1
I:  - Num steps reported: 0
"""
        result = cs_subevent_parser.parse_cs_subevent_result(text_data)
        assert result is None
