import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'toolset', 'cs_utils'))

import cs_step_parser
import cs_step


class TestParseCSSteps:
    """Smoke tests for CS step parser."""

    def test_empty_stream(self):
        """Test parsing empty hex string."""
        result = cs_step_parser.parse_cs_steps("")
        assert result == []

    def test_incomplete_header(self, caplog):
        """Test handling of incomplete header."""
        # Only 2 bytes instead of 3
        result = cs_step_parser.parse_cs_steps("0005")
        assert result == []
        assert "Incomplete step header" in caplog.text

    def test_invalid_mode(self, caplog):
        """Test handling of invalid mode value."""
        # mode=4 (invalid), channel=5, data_len=0
        result = cs_step_parser.parse_cs_steps("040500")
        assert result == []
        assert "Invalid mode 4" in caplog.text

    def test_invalid_channel(self, caplog):
        """Test handling of invalid channel value."""
        # mode=0, channel=79 (invalid), data_len=0
        result = cs_step_parser.parse_cs_steps("004f00")
        assert result == []
        assert "Invalid channel 79" in caplog.text

    def test_incomplete_data(self, caplog):
        """Test handling of incomplete step data."""
        # mode=0, channel=5, data_len=5, but only 3 bytes of data
        result = cs_step_parser.parse_cs_steps("000505aabbcc")
        assert result == []
        assert "Incomplete step data" in caplog.text

    def test_mode0_basic(self):
        """Test parsing Mode 0 step without frequency offset."""
        # mode=0, channel=5, data_len=3, quality=0, rssi=-50 (0xCE), antenna=1
        result = cs_step_parser.parse_cs_steps("00050300ce01")
        assert len(result) == 1
        step = result[0]
        assert step.mode == 0
        assert step.channel == 5
        assert step.packet_quality == 0
        assert step.packet_rssi == -50
        assert step.packet_antenna == 1
        assert step.measured_freq_offset is None

    def test_mode0_with_freq_offset(self):
        """Test parsing Mode 0 step with frequency offset."""
        # mode=0, channel=10, data_len=5, quality=0, rssi=-60 (0xC4), antenna=2, freq_offset=100 (0x6400 little-endian)
        result = cs_step_parser.parse_cs_steps("000a0500c4026400")
        assert len(result) == 1
        step = result[0]
        assert step.mode == 0
        assert step.channel == 10
        assert step.packet_quality == 0
        assert step.packet_rssi == -60
        assert step.packet_antenna == 2
        assert step.measured_freq_offset == 100.0

    def test_mode0_rssi_not_available(self):
        """Test parsing Mode 0 step with RSSI not available."""
        # mode=0, channel=8, data_len=3, quality=0, rssi=0x7F (not available), antenna=0
        result = cs_step_parser.parse_cs_steps("000803007f00")
        assert len(result) == 1
        step = result[0]
        assert step.packet_rssi is None

    def test_mode2_basic(self):
        """Test parsing Mode 2 step with 2 tones."""
        result = cs_step_parser.parse_cs_steps("0205090000f0ff00ff0f001202200d00b8800703b3ff06030380ff13")
        assert len(result) == 2
        step = result[0]
        assert step.mode == 2
        assert step.channel == 5
        assert step.antenna_permutation_index == 0
        assert len(step.tones) == 2
        assert step.tones[0].pct_i == 0
        assert step.tones[0].pct_q == -1
        assert step.tones[0].quality == cs_step.ToneQualityIndicator.TONE_QUALITY_HIGH
        assert step.tones[0].quality_extension_slot == cs_step.ToneQualityIndicatorExtensionSlot.NOT_TONE_EXTENSION_SLOT
        assert step.tones[1].pct_i == -1
        assert step.tones[1].pct_q == 0
        assert step.tones[1].quality == cs_step.ToneQualityIndicator.TONE_QUALITY_LOW
        assert step.tones[1].quality_extension_slot == cs_step.ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED
        step = result[1]
        assert step.mode == 2
        assert step.channel == 32
        assert step.antenna_permutation_index == 0
        assert len(step.tones) == 3
        assert step.tones[0].pct_i == 184
        assert step.tones[0].pct_q == 120
        assert step.tones[0].quality == cs_step.ToneQualityIndicator.TONE_QUALITY_UNAVAILABLE
        assert step.tones[0].quality_extension_slot == cs_step.ToneQualityIndicatorExtensionSlot.NOT_TONE_EXTENSION_SLOT
        assert step.tones[1].pct_i == -77
        assert step.tones[1].pct_q == 111
        assert step.tones[1].quality == cs_step.ToneQualityIndicator.TONE_QUALITY_UNAVAILABLE
        assert step.tones[1].quality_extension_slot == cs_step.ToneQualityIndicatorExtensionSlot.NOT_TONE_EXTENSION_SLOT
        assert step.tones[2].pct_i == 3
        assert step.tones[2].pct_q == -8
        assert step.tones[2].quality == cs_step.ToneQualityIndicator.TONE_QUALITY_UNAVAILABLE
        assert step.tones[2].quality_extension_slot == cs_step.ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED

    def test_mode2_invalid_data_length_too_short(self, caplog):
        """Test Mode 2 with data length that doesn't satisfy (len-1) % 4 == 0."""
        # mode=2, channel=5, data_len=2 (1 antenna byte + 1 extra, invalid)
        result = cs_step_parser.parse_cs_steps("02050200aa")
        assert result == []
        assert "Invalid Mode 2 data length: 2" in caplog.text

    def test_mode2_invalid_data_length_wrong_remainder(self, caplog):
        """Test Mode 2 with data length that doesn't satisfy (len-1) % 4 == 0."""
        # mode=2, channel=5, data_len=3 (1 antenna byte + 2 extra, invalid)
        result = cs_step_parser.parse_cs_steps("020503aabbcc")
        assert result == []
        assert "Invalid Mode 2 data length: 3" in caplog.text

    def test_mode2_invalid_tone_count_zero(self, caplog):
        """Test Mode 2 with k=0 tones (only antenna byte)."""
        # mode=2, channel=5, data_len=1 (just antenna byte, k=0)
        result = cs_step_parser.parse_cs_steps("02050100")
        assert result == []
        assert "Invalid number of tones in Mode 2: 0" in caplog.text

    def test_mode2_invalid_tone_count_one(self, caplog):
        """Test Mode 2 with k=1 tone (below minimum of 2)."""
        # mode=2, channel=5, data_len=5 (1 antenna + 4 bytes = 1 tone, k=1)
        result = cs_step_parser.parse_cs_steps("02050500aabbccdd")
        assert result == []
        assert "Invalid number of tones in Mode 2: 1" in caplog.text

    def test_mode2_invalid_tone_count_six(self, caplog):
        """Test Mode 2 with k=6 tones (above maximum of 5)."""
        # mode=2, channel=5, data_len=25 (1 antenna + 24 bytes = 6 tones, k=6)
        result = cs_step_parser.parse_cs_steps("02051900" + "aa" * 24)
        assert result == []
        assert "Invalid number of tones in Mode 2: 6" in caplog.text

    def test_mode0_mode4_mode2(self, caplog):
        """Test parsing invalid mode between mode 0 and mode 2 steps. Should skip invalid step."""
        # mode=0, channel=5, data_len=3, quality=0, rssi=-50 (0xCE), antenna=1
        # mode=4 (invalid), channel=10, data_len=0
        # mode=2, channel=8, data_len=9, antenna=0, 2 tones
        hex_input = "00050300ce01" + "040a00" + "02080900ff078000ff0f0012"
        result = cs_step_parser.parse_cs_steps(hex_input)
        assert len(result) == 2
        step = result[0]
        assert step.mode == 0
        assert step.channel == 5
        assert step.packet_quality == 0
        assert step.packet_rssi == -50
        assert step.packet_antenna == 1
        step = result[1]
        assert step.mode == 2
        assert step.channel == 8
        assert step.antenna_permutation_index == 0
        assert len(step.tones) == 2
        assert step.tones[0].pct_i == 2047
        assert step.tones[0].pct_q == -2048
        assert step.tones[0].quality == cs_step.ToneQualityIndicator.TONE_QUALITY_HIGH
        assert step.tones[0].quality_extension_slot == cs_step.ToneQualityIndicatorExtensionSlot.NOT_TONE_EXTENSION_SLOT
        assert step.tones[1].pct_i == -1
        assert step.tones[1].pct_q == 0
        assert step.tones[1].quality == cs_step.ToneQualityIndicator.TONE_QUALITY_LOW
        assert step.tones[1].quality_extension_slot == cs_step.ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED
        assert "Invalid mode 4" in caplog.text

