import re
from typing import List, Optional
from cs_utils.cs_subevent_parser import parse_cs_subevent_result
from cs_utils.cs_subevent import SubeventResults


class CSDataProcessor:
    def process_file(self, filepath):
        with open(filepath) as f:
            return self._process_text(f.read())

    def process_uart(self, port):
        # Stream and accumulate
        # TODO: implement reading from device port
        pass

    def _process_text(self, text: str) -> List[Optional[SubeventResults]]:
        """Extract CS Subevent blocks and parse them.

        Args:
            text: Raw log text containing CS Subevent results

        Returns:
            List of parsed SubeventResults objects
        """
        subevents = []

        # Split text by "CS Subevent result received:" marker
        # Keep the marker in each block by using positive lookahead
        pattern = r'(?=I: CS Subevent result received:)'
        # TODO: add marker at the end to make parsing easier
        blocks = re.split(pattern, text)

        for block in blocks:
            # Skip empty blocks or blocks without the marker
            if not block.strip() or 'CS Subevent result received:' not in block:
                continue

            # Extract the subevent block until next "CS Subevent result received:" or EOF
            # Find where this block ends (next marker or end of string)
            next_marker = block.find('I: CS Subevent result received:', 1)
            if next_marker != -1:
                subevent_text = block[:next_marker]
            else:
                subevent_text = block

            # Parse the subevent
            parsed_subevent = parse_cs_subevent_result(subevent_text)
            subevents.append(parsed_subevent)

        return subevents