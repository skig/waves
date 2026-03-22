from dataclasses import dataclass
from typing import List, Tuple


# Bitmask-to-value lookup tables for timing fields

T_IP1_VALUES_US = {0: 10, 1: 20, 2: 30, 3: 40, 4: 50, 5: 60, 6: 80}
T_IP2_VALUES_US = {0: 10, 1: 20, 2: 30, 3: 40, 4: 50, 5: 60, 6: 80}
T_FCS_VALUES_US = {0: 15, 1: 20, 2: 30, 3: 40, 4: 50, 5: 60, 6: 80, 7: 100, 8: 120}
T_PM_VALUES_US = {0: 10, 1: 20}
SNR_VALUES_DB = {0: 18, 1: 21, 2: 24, 3: 27, 4: 30}

ROLES_BITS = {0: 'Initiator', 1: 'Reflector'}
MODES_BITS = {0: 'Mode-3'}
RTT_CAPABILITY_BITS = {0: 'AA_Only 10ns', 1: 'Sounding 10ns', 2: 'Random 10ns'}
NADM_SOUNDING_BITS = {0: 'Phase-based'}
NADM_RANDOM_BITS = {0: 'Phase-based'}
CS_SYNC_PHYS_BITS = {1: '2M PHY', 2: '2M 2BT PHY'}
SUBFEATURES_BITS = {1: 'No FAE', 2: 'ChSel #3c', 3: 'PBR from RTT'}


# Display segment: (text, active) — active=True for normal, False for greyed out
Segment = Tuple[str, bool]


def _decode_bitmask(bitmask: int, bit_to_value: dict) -> List[int]:
    return [val for bit, val in sorted(bit_to_value.items()) if bitmask & (1 << bit)]


def _bitmask_segments(bitmask: int, bit_to_label: dict) -> List[Segment]:
    items = sorted(bit_to_label.items())
    return [(label + ',' if i < len(items) - 1 else label, bool(bitmask & (1 << bit)))
            for i, (bit, label) in enumerate(items)]


def _value_bitmask_segments(bitmask: int, bit_to_value: dict, unit: str = '') -> List[Segment]:
    segments = []
    for bit, val in sorted(bit_to_value.items()):
        segments.append((str(val), bool(bitmask & (1 << bit))))
    if unit:
        any_active = any(active for _, active in segments)
        segments.append((unit.lstrip(), any_active))
    return segments


# Display line: (label, segments_list)
DisplayLine = Tuple[str, List[Segment]]


@dataclass
class CSCapabilities:
    """Channel Sounding capabilities as defined in Core Spec v6.0,
    Vol 4, Part E, Section 7.7.65.39
    (LE CS Read Remote Supported Capabilities Complete event).

    Field names and types match the HCI event parameters from the spec.
    Bitmask fields are stored as raw ints; use helper properties to decode.
    """

    num_config_supported: int
    max_consecutive_procedures_supported: int
    num_antennas_supported: int
    max_antenna_paths_supported: int
    roles_supported: int
    modes_supported: int
    rtt_capability: int
    rtt_aa_only_n: int
    rtt_sounding_n: int
    rtt_random_payload_n: int
    nadm_sounding_capability: int
    nadm_random_capability: int
    cs_sync_phys_supported: int
    subfeatures_supported: int
    t_ip1_times_supported: int
    t_ip2_times_supported: int
    t_fcs_times_supported: int
    t_pm_times_supported: int
    t_sw_time_supported: int
    tx_snr_capability: int

    @classmethod
    def from_text(cls, text: str) -> 'CSCapabilities':
        """Parse capabilities from log text lines.

        Expected format (one field per line):
            Num_Config_Supported: 1
            Roles_Supported: 0x02
            T_IP1_Times_Supported: 0x007c
        """
        fields = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, _, value = line.partition(':')
            fields[key.strip()] = value.strip()

        def _int(name: str) -> int:
            v = fields.get(name, '0')
            return int(v, 16) if v.startswith('0x') or v.startswith('0X') else int(v)

        return cls(
            num_config_supported=_int('Num_Config_Supported'),
            max_consecutive_procedures_supported=_int('Max_Consecutive_Procedures_Supported'),
            num_antennas_supported=_int('Num_Antennas_Supported'),
            max_antenna_paths_supported=_int('Max_Antenna_Paths_Supported'),
            roles_supported=_int('Roles_Supported'),
            modes_supported=_int('Modes_Supported'),
            rtt_capability=_int('RTT_Capability'),
            rtt_aa_only_n=_int('RTT_AA_Only_N'),
            rtt_sounding_n=_int('RTT_Sounding_N'),
            rtt_random_payload_n=_int('RTT_Random_Payload_N'),
            nadm_sounding_capability=_int('NADM_Sounding_Capability'),
            nadm_random_capability=_int('NADM_Random_Capability'),
            cs_sync_phys_supported=_int('CS_SYNC_PHYs_Supported'),
            subfeatures_supported=_int('Subfeatures_Supported'),
            t_ip1_times_supported=_int('T_IP1_Times_Supported'),
            t_ip2_times_supported=_int('T_IP2_Times_Supported'),
            t_fcs_times_supported=_int('T_FCS_Times_Supported'),
            t_pm_times_supported=_int('T_PM_Times_Supported'),
            t_sw_time_supported=_int('T_SW_Time_Supported'),
            tx_snr_capability=_int('TX_SNR_Capability'),
        )

    def display_lines(self) -> List[DisplayLine]:
        """Return structured lines for GUI rendering.

        Each line is (label, segments) where segments is a list of
        (text, active) tuples. Active segments render normally;
        inactive segments render greyed out.
        """
        return [
            ('Num_Config_Supported', [(str(self.num_config_supported), True)]),
            ('Max_Consecutive_Procedures_Supported', [(str(self.max_consecutive_procedures_supported), True)]),
            ('Num_Antennas_Supported', [(str(self.num_antennas_supported), True)]),
            ('Max_Antenna_Paths_Supported', [(str(self.max_antenna_paths_supported), True)]),
            ('Roles_Supported', _bitmask_segments(self.roles_supported, ROLES_BITS)),
            ('Modes_Supported', _bitmask_segments(self.modes_supported, MODES_BITS)),
            ('RTT_Capability', _bitmask_segments(self.rtt_capability, RTT_CAPABILITY_BITS)),
            ('RTT_AA_Only_N', [(str(self.rtt_aa_only_n), self.rtt_aa_only_n != 0)]),
            ('RTT_Sounding_N', [(str(self.rtt_sounding_n), self.rtt_sounding_n != 0)]),
            ('RTT_Random_Payload_N', [(str(self.rtt_random_payload_n), self.rtt_random_payload_n != 0)]),
            ('NADM_Sounding_Capability', _bitmask_segments(self.nadm_sounding_capability, NADM_SOUNDING_BITS)),
            ('NADM_Random_Capability', _bitmask_segments(self.nadm_random_capability, NADM_RANDOM_BITS)),
            ('CS_SYNC_PHYs_Supported', _bitmask_segments(self.cs_sync_phys_supported, CS_SYNC_PHYS_BITS)),
            ('Subfeatures_Supported', _bitmask_segments(self.subfeatures_supported, SUBFEATURES_BITS)),
            ('T_IP1_Times_Supported', _value_bitmask_segments(self.t_ip1_times_supported, T_IP1_VALUES_US, ' μs')),
            ('T_IP2_Times_Supported', _value_bitmask_segments(self.t_ip2_times_supported, T_IP2_VALUES_US, ' μs')),
            ('T_FCS_Times_Supported', _value_bitmask_segments(self.t_fcs_times_supported, T_FCS_VALUES_US, ' μs')),
            ('T_PM_Times_Supported', _value_bitmask_segments(self.t_pm_times_supported, T_PM_VALUES_US, ' μs')),
            ('T_SW_Time_Supported', [(f'{self.t_sw_time_supported} μs', True)]),
            ('TX_SNR_Capability', _value_bitmask_segments(self.tx_snr_capability, SNR_VALUES_DB, ' dB')),
        ]

    @property
    def supported_t_ip1_times_us(self) -> List[int]:
        return _decode_bitmask(self.t_ip1_times_supported, T_IP1_VALUES_US)

    @property
    def supported_t_ip2_times_us(self) -> List[int]:
        return _decode_bitmask(self.t_ip2_times_supported, T_IP2_VALUES_US)

    @property
    def supported_t_fcs_times_us(self) -> List[int]:
        return _decode_bitmask(self.t_fcs_times_supported, T_FCS_VALUES_US)

    @property
    def supported_t_pm_times_us(self) -> List[int]:
        return _decode_bitmask(self.t_pm_times_supported, T_PM_VALUES_US)

    @property
    def supported_snr_levels_db(self) -> List[int]:
        return _decode_bitmask(self.tx_snr_capability, SNR_VALUES_DB)
