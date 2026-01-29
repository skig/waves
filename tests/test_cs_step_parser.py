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

