import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional
from toolset.cs_utils.cs_capabilities import CSCapabilities
from toolset.gui.cs_theme import _Theme

_CAPABILITY_DESC_DEFAULT = 'Before performing CS procedure, devices exchange their CS capabilities, the capabilities reported by Reflector device are shown above. Click on a capability to see details. Greyed-out values are not supported by the device, bright values are supported.'

_CAPABILITY_DESCRIPTIONS: Dict[str, str] = {
    'Num_Config_Supported': 'Before performing CS procedure, initiator and reflector negotiate what CS configuration they will use: step modes, timings etc. A device can store from 1 to 4 different CS configurations, the number of supported CS configurations is defined by Num_Config_Supported.',
    'Max_Consecutive_Procedures_Supported': 'Maximum number of consecutive CS procedures the device supports. Can be from 1 to 65535, or indefinite, in which case the CS procedures run until CS procedure termination is performed (shown as ∞).',
    'Num_Antennas_Supported': 'Number of antennas a device has available for CS.',
    'Max_Antenna_Paths_Supported': 'Maximum number of antenna paths supported during CS. Note, a device can have only a single antenna but still support multiple paths, in that case the peer needs to perform antenna switching.',
    'Roles_Supported': 'A device can support both roles (initiator and reflector), or just a single one.',
    'Modes_Supported': 'Optional CS step modes supported. Mode-0, mode-1 and mode-2 are mandatory so they are not included in capabilities exchange procedure, only mode-3 is optional and may or may not be supported by the device.',
    'RTT_Capability': 'Optional 10-ns RTT accuracy support. If 10-ns accuracy is not supported, the device supports mandatory 150 ns accuracy on the supported RTT packet formats (see 3 capabilities below).',
    'RTT_AA_Only_N': 'Number of AA-only RTT packets required to achieve the specified accuracy (10 ns or 150 ns). If 0, then AA-only RTT packets are not supported.',
    'RTT_Sounding_N': 'Number of Sounding RTT packets required to achieve the specified accuracy (10 ns or 150 ns). If 0, then Sounding RTT packets are not supported.',
    'RTT_Random_Payload_N': 'Number of random-payload RTT packets required to achieve the specified accuracy (10 ns or 150 ns). If 0, then random-payload RTT packets are not supported.',
    'NADM_Sounding_Capability': 'Normalized Attack Detector Metric capability for sounding sequences.',
    'NADM_Random_Capability': 'Normalized Attack Detector Metric capability for random sequences.',
    'CS_SYNC_PHYs_Supported': 'Optional PHYs supported for CS procedure. LE 1M PHY is mandatory so it is not included in capabilities exchange procedure. LE 2M and LE 2M 2BT PHYs are optional.',
    'Subfeatures_Supported': 'Optional CS sub-features supported by the device.',
    'T_IP1_Times_Supported': 'Optional interlude period T_IP1 durations. 145 us is mandatory. T_IP1 is time between end of initiator packet and start of reflector packet for mode-0 and mode-1 steps.',
    'T_IP2_Times_Supported': 'Optional interlude period T_IP2 durations. 145 us is mandatory. T_IP2 is time between end of initiator packet and start of reflector packet for mode-2 and mode-3 steps.',
    'T_FCS_Times_Supported': 'Optional frequency hop T_FCS durations. 150 us is mandatory. Frequency hopping happens between steps.',
    'T_PM_Times_Supported': 'Optional phase measurement T_PM durations. 40 us is mandatory. T_PM is the time between when a device receives a CS tone and when it measures the phase and amplitude in a mode-2 or mode-3 step.',
    'T_SW_Time_Supported': 'Antenna switch time T_SW in microseconds. When antenna switching is not supported, the value is 0.',
    'TX_SNR_Capability': 'Signal-to-noise ratio levels used in RTT packets when SNR output control is supported.',
}


class SetupTabMixin:
    """CS setup tab: connection status indicators and capabilities display."""

    def _build_setup_tab(self, tab_frame: ttk.Frame):
        _SETUP_FIELDS = [
            ('connection', 'Connection'),
            ('encryption', 'Connection encryption'),
            ('cs_security', 'CS Security'),
            ('cs_capabilities', 'CS Capabilities exchange'),
            ('cs_config', 'CS Configuration'),
            ('cs_procedure', 'CS Procedure'),
        ]
        self._setup_indicators: Dict[str, tk.Canvas] = {}

        container = ttk.Frame(tab_frame)
        container.grid(row=0, column=0, sticky=tk.NW, padx=20, pady=20)

        for row, (key, label) in enumerate(_SETUP_FIELDS):
            indicator = tk.Canvas(container, width=16, height=16,
                                  bg=_Theme.Background, highlightthickness=0)
            indicator.create_oval(2, 2, 14, 14, fill='#b71c1c', outline='', tags='dot')
            indicator.grid(row=row, column=0, padx=(0, 10), pady=4)
            self._setup_indicators[key] = indicator

            ttk.Label(container, text=label, font=('TkDefaultFont', 11)).grid(
                row=row, column=1, sticky=tk.W, pady=4)

        num_status_rows = len(_SETUP_FIELDS)

        ttk.Label(container, text='CS subevent period:', font=('TkDefaultFont', 11)).grid(
            row=num_status_rows, column=0, sticky=tk.W, pady=(8, 4))
        self._subevent_period_label = ttk.Label(container, text='—', font=('TkDefaultFont', 11))
        self._subevent_period_label.grid(row=num_status_rows, column=1, sticky=tk.W, pady=(8, 4))

        num_status_rows += 1

        ttk.Label(container, text='CS capabilities (reflector):', font=('TkDefaultFont', 11)).grid(
            row=num_status_rows, column=0, columnspan=2, sticky=tk.W, pady=(16, 4))

        self._capabilities_text = tk.Text(
            container, height=20, width=60, wrap='none',
            bg=_Theme.AltBackground, fg=_Theme.Foreground,
            insertbackground=_Theme.Foreground,
            font=('TkFixedFont', 10),
            cursor='arrow',
        )
        self._capabilities_text.tag_configure('active', foreground=_Theme.Foreground)
        self._capabilities_text.tag_configure('inactive', foreground=_Theme.SubtleForeground)
        self._capabilities_text.tag_configure('label', foreground=_Theme.MidForeground)
        self._capabilities_text.tag_configure('line_selected', background=_Theme.Selection)
        self._capabilities_text.tag_raise('line_selected')
        self._capabilities_text.bind('<Button-1>', self._on_capabilities_click)
        self._capabilities_text.bind('<B1-Motion>', lambda e: 'break')
        self._capabilities_text.bind('<Double-Button-1>', lambda e: 'break')
        self._capabilities_text.bind('<Triple-Button-1>', lambda e: 'break')
        self._capabilities_text.bind('<Up>', lambda e: (self._on_capabilities_key_navigate(-1), 'break')[1])
        self._capabilities_text.bind('<Down>', lambda e: (self._on_capabilities_key_navigate(1), 'break')[1])
        self._capabilities_text.bind('<Control-c>', self._on_capabilities_copy)
        self._capabilities_text.bind('<Escape>', self._on_capabilities_deselect)
        self._capabilities_text.grid(
            row=num_status_rows + 1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 4))
        self._capabilities_text.insert('1.0', 'No data')
        self._capabilities_text.config(state=tk.DISABLED)

        ttk.Label(container, text='Capability description:', font=('TkDefaultFont', 11)).grid(
            row=num_status_rows + 2, column=0, columnspan=2, sticky=tk.W, pady=(8, 4))

        self._capability_desc_text = tk.Text(
            container, height=6, width=60, wrap='word',
            bg=_Theme.AltBackground, fg=_Theme.Foreground,
            insertbackground=_Theme.Foreground,
            font=('TkFixedFont', 10),
        )
        self._capability_desc_text.grid(
            row=num_status_rows + 3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 4))
        self._capability_desc_text.insert('1.0', _CAPABILITY_DESC_DEFAULT)
        self._capability_desc_text.config(state=tk.DISABLED)

    def _update_setup_tab(self):
        pass

    def update_connection_status(self, key: str):
        """Update a CS setup indicator to green. Thread-safe."""
        def _set():
            indicator = self._setup_indicators.get(key)
            if indicator:
                indicator.delete('dot')
                indicator.create_oval(2, 2, 14, 14, fill='#2e7d32', outline='', tags='dot')
        self.root.after(0, _set)

    def update_procedure_params(self, connection_interval_ms: int, procedure_interval: int):
        """Update the subevent period label from ACL and procedure intervals. Thread-safe."""
        period_ms = connection_interval_ms * procedure_interval
        text = f'{period_ms} ms  ({connection_interval_ms} ms × {procedure_interval})'
        self.root.after(0, lambda: self._subevent_period_label.config(text=text))

    def update_capabilities_text(self, text: str):
        """Parse capabilities text and render with active/greyed segments. Thread-safe."""
        try:
            caps = CSCapabilities.from_text(text)
        except Exception:
            self.root.after(0, lambda: self._set_capabilities_plain(text))
            return
        self.root.after(0, lambda: self._render_capabilities(caps))

    def _set_capabilities_plain(self, text: str):
        self._capabilities_text.config(state=tk.NORMAL)
        self._capabilities_text.delete('1.0', tk.END)
        self._capabilities_text.insert('1.0', text)
        self._capabilities_text.config(state=tk.DISABLED)

    def _render_capabilities(self, caps: CSCapabilities):
        w = self._capabilities_text
        w.config(state=tk.NORMAL)
        w.delete('1.0', tk.END)
        self._capabilities_labels = []
        for i, (label, segments) in enumerate(caps.display_lines()):
            if i > 0:
                w.insert(tk.END, '\n')
            w.insert(tk.END, f'{label}: ', 'label')
            for j, (seg_text, active) in enumerate(segments):
                if j > 0:
                    w.insert(tk.END, '  ', 'inactive')
                tag = 'active' if active else 'inactive'
                w.insert(tk.END, seg_text, tag)
            self._capabilities_labels.append(label)
        w.config(state=tk.DISABLED)
        self._selected_capability_line = None
        self._set_text_widget(self._capability_desc_text, _CAPABILITY_DESC_DEFAULT)

    def _on_capabilities_copy(self, event):
        """Copy capabilities text with only active (highlighted) values to clipboard."""
        w = self._capabilities_text

        def _tag_texts_on_line(tag, line):
            texts = []
            ranges = w.tag_ranges(tag)
            for i in range(0, len(ranges), 2):
                if int(str(ranges[i]).split('.')[0]) == line:
                    texts.append(w.get(ranges[i], ranges[i + 1]))
            return texts

        num_lines = int(w.index('end-1c').split('.')[0])
        result_lines = []
        for line_num in range(1, num_lines + 1):
            label = ''.join(_tag_texts_on_line('label', line_num))
            active = '  '.join(_tag_texts_on_line('active', line_num))
            result_lines.append(label + (active if active.strip() else 'None'))

        self.root.clipboard_clear()
        self.root.clipboard_append('\n'.join(result_lines))
        return 'break'

    def _on_capabilities_deselect(self, event):
        """Deselect capability line and restore default description."""
        w = self._capabilities_text
        w.config(state=tk.NORMAL)
        w.tag_remove('line_selected', '1.0', tk.END)
        w.config(state=tk.DISABLED)
        self._selected_capability_line = None
        self._set_text_widget(self._capability_desc_text, _CAPABILITY_DESC_DEFAULT)
        return 'break'

    def _on_capabilities_click(self, event):
        """Select whole line in capabilities text and show description."""
        idx = self._capabilities_text.index(f'@{event.x},{event.y}')
        line_num = int(idx.split('.')[0])
        self._select_capability_line(line_num)
        self._capabilities_text.focus_set()
        return 'break'

    def _on_capabilities_key_navigate(self, delta: int):
        """Move capability selection up or down by delta lines."""
        if not self._capabilities_labels:
            return
        current = self._selected_capability_line if self._selected_capability_line is not None else -1
        new_idx = max(0, min(len(self._capabilities_labels) - 1, current + delta))
        self._select_capability_line(new_idx + 1)

    def _select_capability_line(self, line_num: int):
        w = self._capabilities_text
        w.config(state=tk.NORMAL)
        w.tag_remove('line_selected', '1.0', tk.END)
        w.tag_add('line_selected', f'{line_num}.0', f'{line_num}.end')
        w.config(state=tk.DISABLED)

        cap_idx = line_num - 1
        self._selected_capability_line = cap_idx
        if 0 <= cap_idx < len(self._capabilities_labels):
            label = self._capabilities_labels[cap_idx]
            desc = _CAPABILITY_DESCRIPTIONS.get(label, 'No description available.')
        else:
            desc = 'No description available.'
        self._set_text_widget(self._capability_desc_text, desc)
