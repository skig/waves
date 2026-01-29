import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'toolset'))

import cs_step_parser


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

