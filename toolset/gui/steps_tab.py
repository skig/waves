import math
import tkinter as tk
from tkinter import ttk
from typing import List, Optional
from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.cs_utils.cs_step import (
    CSMode,
    CSStepMode0,
    CSStepMode2,
    PacketQuality,
    ToneQualityIndicator,
    ToneQualityIndicatorExtensionSlot,
)
from toolset.gui.cs_theme import _Theme

_STEP_VIS_CELL_W = 34    # width for a single-packet rect (modes 0, 1, 3)
_STEP_VIS_TONE_W = 20    # width per tone rect (mode 2)
_STEP_VIS_RECT_H = 42    # row height
_STEP_VIS_STEP_GAP = 6   # horizontal gap between consecutive step groups
_STEP_VIS_PAD_X = 8      # left/right canvas padding
_STEP_VIS_PAD_Y = 5      # top/bottom canvas padding


class StepsTabMixin:
    """Subevent steps tab: hex view, step canvas, and step details."""

    def _create_hex_text_widget(self, parent: ttk.Frame, row: int, col: int, padx) -> tk.Text:
        container = ttk.Frame(parent)
        container.grid(row=row, column=col, sticky=(tk.W, tk.E, tk.N, tk.S), padx=padx)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        text = tk.Text(container, wrap='none', font=('Courier', 12),
                       state=tk.DISABLED, cursor='arrow', width=50,
                       bg=_Theme.Background, fg=_Theme.Foreground,
                       insertbackground=_Theme.Foreground)
        sb_y = ttk.Scrollbar(container, orient=tk.VERTICAL, command=text.yview)
        sb_x = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=text.xview)
        text.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        sb_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        sb_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        return text

    def _create_details_text_widget(self, parent: ttk.Frame, row: int, col: int, padx) -> tk.Text:
        container = ttk.Frame(parent)
        container.grid(row=row, column=col, sticky=(tk.W, tk.E, tk.N, tk.S), padx=padx)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        text = tk.Text(container, wrap='word', font=('Courier', 12), state=tk.DISABLED,
                       bg=_Theme.Background, fg=_Theme.Foreground,
                       insertbackground=_Theme.Foreground)
        sb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        sb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        return text

    def _highlight_selected_step_in_canvas(self, step_idx: int):
        self.steps_canvas.delete('step_highlight')
        if step_idx >= len(self._step_canvas_regions):
            return
        x1, x2 = self._step_canvas_regions[step_idx]
        y1 = _STEP_VIS_PAD_Y - 2
        y2 = _STEP_VIS_PAD_Y + _STEP_VIS_RECT_H + 2
        self.steps_canvas.create_rectangle(
            x1 - 1, y1, x2, y2,
            outline=_Theme.SelectionBorder, width=5, fill='', tags='step_highlight',
        )
        self.steps_canvas.tag_raise('step_highlight')
        # Scroll to keep the selected step visible
        scrollregion = self.steps_canvas.cget('scrollregion')
        if scrollregion:
            try:
                total_w = float(scrollregion.split()[2])
                if total_w > 0:
                    cur_l, cur_r = self.steps_canvas.xview()
                    left_frac = max(0.0, (x1 - 10) / total_w)
                    right_frac = min(1.0, (x2 + 10) / total_w)
                    if left_frac < cur_l or right_frac > cur_r:
                        self.steps_canvas.xview_moveto(left_frac)
            except (ValueError, IndexError):
                pass

    def _tag_bytes_in_widget(self, widget: tk.Text, tag: str, byte_start: int, byte_end: int):
        """Apply tag to hex characters for bytes [byte_start, byte_end) in the text widget."""
        if byte_end <= byte_start:
            return
        row_start = byte_start // 16
        row_end = (byte_end - 1) // 16
        for r in range(row_start, row_end + 1):
            first = max(byte_start, r * 16)
            last = min(byte_end - 1, r * 16 + 15)
            line_num = r + 1
            cs = (first % 16) * 3
            lk = last % 16
            # Include trailing space only when it's within the row (not the last column)
            ce = lk * 3 + (3 if lk < 15 else 2)
            widget.tag_add(tag, f'{line_num}.{cs}', f'{line_num}.{ce}')

    def _update_hex_selection(self, widget: tk.Text, step_ranges: List[tuple], selected_idx: int):
        widget.config(state=tk.NORMAL)
        widget.tag_remove('step_selected', '1.0', tk.END)
        if 0 <= selected_idx < len(step_ranges):
            start, end = step_ranges[selected_idx]
            self._tag_bytes_in_widget(widget, 'step_selected', start, end)
            widget.tag_raise('step_selected')
            line = start // 16 + 1
            widget.see(f'{line}.0')
        widget.config(state=tk.DISABLED)

    def _format_step_details(self, step) -> str:
        if step is None:
            return 'N/A'

        lines = [f'Mode:    {step.mode.value}', f'Channel: {step.channel}']

        if isinstance(step, CSStepMode0):
            lines.append(f'Packet Quality:  {step.packet_quality.name}')
            lines.append(
                f'RSSI:            {step.packet_rssi} dBm'
                if step.packet_rssi is not None
                else 'RSSI:            N/A'
            )
            lines.append(f'Packet Antenna:  {step.packet_antenna}')
            if step.measured_freq_offset is not None:
                lines.append(f'Freq Offset:     {step.measured_freq_offset / 100:.4f} ppm')

        elif isinstance(step, CSStepMode2):
            lines.append(f'Antenna Permutation: {step.antenna_permutation_index}')
            for i, tone in enumerate(step.tones):
                mag = math.sqrt(tone.pct_i ** 2 + tone.pct_q ** 2)
                phase = math.atan2(tone.pct_q, tone.pct_i)
                if tone.quality_extension_slot != ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED:
                    lines.append(
                        f'Tone {i}:  I={tone.pct_i:<6} Q={tone.pct_q:<6} '
                        f'Mag={mag:>8.2f}  Phase={phase:>7.4f}  '
                        f'Quality={tone.quality.short_description()}'
                    )
                else:
                    lines.append(f'Tone {i} (extension slot not expected): Mag={mag:.2f}')

        elif hasattr(step, 'raw_data'):
            lines.append(f'Raw: {step.raw_data.hex()}')

        return '\n'.join(lines)

    def _select_step(self, step_idx: int):
        self._selected_step_idx = step_idx
        self._update_hex_selection(self.ini_hex_text, self._ini_step_ranges, step_idx)
        self._update_hex_selection(self.ref_hex_text, self._ref_step_ranges, step_idx)

        ini_step = (
            self._current_initiator.steps[step_idx]
            if self._current_initiator and step_idx < len(self._current_initiator.steps)
            else None
        )
        ref_step = (
            self._current_reflector.steps[step_idx]
            if self._current_reflector and step_idx < len(self._current_reflector.steps)
            else None
        )

        details = (
            f'--- Initiator Step {step_idx} ---\n'
            f'{self._format_step_details(ini_step)}'
            f'\n\n--- Reflector Step {step_idx} ---\n'
            f'{self._format_step_details(ref_step)}'
        )
        self._set_text_widget(self.step_details_text, details)
        self._highlight_selected_step_in_canvas(step_idx)

    def _on_steps_canvas_click(self, event):
        canvas_x = self.steps_canvas.canvasx(event.x)
        step_idx = next(
            (i for i, (x1, x2) in enumerate(self._step_canvas_regions) if x1 <= canvas_x < x2),
            None,
        )
        if step_idx is not None:
            self._select_step(step_idx)
            self.steps_canvas.focus_set()

    def _on_hex_key_navigate(self, delta: int):
        max_step = max(len(self._ini_step_ranges), len(self._ref_step_ranges)) - 1
        if max_step < 0:
            return
        current = self._selected_step_idx if self._selected_step_idx is not None else 0
        new_idx = max(0, min(max_step, current + delta))
        if new_idx != self._selected_step_idx:
            self._select_step(new_idx)

    def _bind_nav_keys(self, widget: tk.BaseWidget):
        widget.bind('<Left>',  lambda e: (self._on_hex_key_navigate(-1), 'break')[1])
        widget.bind('<Right>', lambda e: (self._on_hex_key_navigate(+1), 'break')[1])
        widget.bind('<Up>',    lambda e: (self._on_hex_key_navigate(-2), 'break')[1])
        widget.bind('<Down>',  lambda e: (self._on_hex_key_navigate(+2), 'break')[1])

    def _on_hex_click(self, event, source: str):
        widget = self.ini_hex_text if source == 'ini' else self.ref_hex_text
        step_ranges = self._ini_step_ranges if source == 'ini' else self._ref_step_ranges

        idx = widget.index(f'@{event.x},{event.y}')
        line, col = map(int, idx.split('.'))
        byte_offset = (line - 1) * 16 + col // 3

        step_idx = next(
            (i for i, (start, end) in enumerate(step_ranges) if start <= byte_offset < end),
            None,
        )
        if step_idx is None:
            return
        self._select_step(step_idx)

    def _build_stats_tab(self, tab_frame: ttk.Frame):
        # --- Summary statistics (top) ---
        stats_frame = ttk.Frame(tab_frame)
        stats_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 6))
        stats_frame.columnconfigure(1, weight=1)

        ttk.Label(stats_frame, text='Initiator Statistics:').grid(row=0, column=0, sticky=tk.NW, pady=3)
        self.initiator_stats_text = tk.Text(
            stats_frame, height=2, wrap='word',
            bg=_Theme.Background, fg=_Theme.Foreground,
            insertbackground=_Theme.Foreground,
        )
        self.initiator_stats_text.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=3, padx=(10, 0))
        self.initiator_stats_text.config(state=tk.DISABLED)

        ttk.Label(stats_frame, text='Reflector Statistics:').grid(row=1, column=0, sticky=tk.NW, pady=3)
        self.reflector_stats_text = tk.Text(
            stats_frame, height=2, wrap='word',
            bg=_Theme.Background, fg=_Theme.Foreground,
            insertbackground=_Theme.Foreground,
        )
        self.reflector_stats_text.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=3, padx=(10, 0))
        self.reflector_stats_text.config(state=tk.DISABLED)

        # --- Steps visualization ---
        steps_vis_frame = ttk.Frame(tab_frame)
        steps_vis_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 4))
        steps_vis_frame.columnconfigure(0, weight=1)

        ttk.Label(steps_vis_frame, text='Steps:').grid(row=0, column=0, sticky=tk.W, pady=(0, 2))

        canvas_container = ttk.Frame(steps_vis_frame)
        canvas_container.grid(row=1, column=0, sticky=(tk.W, tk.E))
        canvas_container.columnconfigure(0, weight=1)

        _canvas_h = _STEP_VIS_PAD_Y * 2 + _STEP_VIS_RECT_H
        self.steps_canvas = tk.Canvas(canvas_container, height=_canvas_h, bg=_Theme.CanvasBackground, cursor='arrow')
        steps_hscroll = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.steps_canvas.xview)
        self.steps_canvas.configure(xscrollcommand=steps_hscroll.set)
        self.steps_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E))
        steps_hscroll.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.steps_canvas.bind('<Button-1>', self._on_steps_canvas_click)
        self._bind_nav_keys(self.steps_canvas)

        # --- Hex + details panel (bottom, three equal columns) ---
        hex_detail_frame = ttk.Frame(tab_frame)
        hex_detail_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        hex_detail_frame.columnconfigure(0, weight=1)
        hex_detail_frame.columnconfigure(1, weight=1)
        hex_detail_frame.columnconfigure(2, weight=1)
        hex_detail_frame.rowconfigure(1, weight=1)

        ttk.Label(hex_detail_frame, text='Initiator Raw Data:').grid(
            row=0, column=0, sticky=tk.W, pady=(0, 3))
        self.ini_hex_text = self._create_hex_text_widget(hex_detail_frame, row=1, col=0, padx=(0, 4))
        self.ini_hex_text.bind('<Button-1>', lambda e: self._on_hex_click(e, 'ini'))
        self._bind_nav_keys(self.ini_hex_text)

        ttk.Label(hex_detail_frame, text='Reflector Raw Data:').grid(
            row=0, column=1, sticky=tk.W, pady=(0, 3), padx=4)
        self.ref_hex_text = self._create_hex_text_widget(hex_detail_frame, row=1, col=1, padx=4)
        self.ref_hex_text.bind('<Button-1>', lambda e: self._on_hex_click(e, 'ref'))
        self._bind_nav_keys(self.ref_hex_text)

        ttk.Label(hex_detail_frame, text='Selected Step Details:').grid(
            row=0, column=2, sticky=tk.W, pady=(0, 3), padx=(4, 0))
        self.step_details_text = self._create_details_text_widget(hex_detail_frame, row=1, col=2, padx=(4, 0))

        tab_frame.columnconfigure(0, weight=1)
        tab_frame.rowconfigure(2, weight=1)

    def _get_step_ranges(self, subevent: Optional[SubeventResults]) -> List[tuple]:
        if subevent is None or subevent.step_byte_ranges is None:
            return []
        return subevent.step_byte_ranges

    def _get_step_cells(self, step, role: str) -> List[tuple]:
        """Return list of (label, bg_color, text_color) cells for one side of a step."""
        if step is None:
            return [(role, _Theme.StepMissingBackground, _Theme.StepMissingForeground)]

        mode_num = step.mode.value
        channel = step.channel

        if isinstance(step, CSStepMode0):
            if step.packet_quality == PacketQuality.AA_SUCCESS:
                bg, fg = _Theme.StepGoodBackground, _Theme.StepGoodForeground
            else:
                bg, fg = _Theme.StepBadBackground, _Theme.StepBadForeground
            return [(f'{role}\n{mode_num}\n{channel}', bg, fg)]

        if isinstance(step, CSStepMode2):
            cells = []
            for tone in step.tones:
                if tone.quality_extension_slot == ToneQualityIndicatorExtensionSlot.TONE_EXTENSION_NOT_EXPECTED:
                    color, fg = _Theme.ToneExtensionBackground, _Theme.ToneExtensionForeground
                elif tone.quality == ToneQualityIndicator.TONE_QUALITY_HIGH:
                    color, fg = _Theme.ToneHighBackground, _Theme.ToneHighForeground
                elif tone.quality == ToneQualityIndicator.TONE_QUALITY_MEDIUM:
                    color, fg = _Theme.ToneMediumBackground, _Theme.ToneMediumForeground
                else:
                    color, fg = _Theme.ToneLowBackground, _Theme.ToneLowForeground
                cells.append((f'{role}\n{mode_num}\n{channel}', color, fg))
            return cells or [(f'{role}\n{mode_num}\n{channel}', _Theme.StepDefaultBackground, _Theme.StepDefaultForeground)]

        # Mode 1, 3, or unrecognised
        return [(f'{role}\n{mode_num}\n{channel}', _Theme.StepDefaultBackground, _Theme.StepDefaultForeground)]

    def _redraw_steps_canvas(self):
        canvas = self.steps_canvas
        canvas.delete('all')
        self._step_canvas_regions = []

        ini_steps = self._current_initiator.steps if self._current_initiator else []
        ref_steps = self._current_reflector.steps if self._current_reflector else []
        num_steps = max(len(ini_steps), len(ref_steps))

        canvas_h = _STEP_VIS_PAD_Y * 2 + _STEP_VIS_RECT_H

        if num_steps == 0:
            msg = 'waiting for data...' if self.live_mode else 'no data'
            canvas.create_text(_STEP_VIS_PAD_X, canvas_h // 2, text=msg, anchor='w', fill=_Theme.SubtleForeground)
            canvas.configure(scrollregion=(0, 0, 200, canvas_h))
            return

        x = _STEP_VIS_PAD_X
        y = _STEP_VIS_PAD_Y

        for i in range(num_steps):
            ini = ini_steps[i] if i < len(ini_steps) else None
            ref = ref_steps[i] if i < len(ref_steps) else None

            ini_cells = self._get_step_cells(ini, 'I')
            ref_cells = self._get_step_cells(ref, 'R')
            all_cells = ini_cells + ref_cells
            n_cols = len(all_cells)
            cell_w = _STEP_VIS_TONE_W if max(len(ini_cells), len(ref_cells)) > 1 else _STEP_VIS_CELL_W
            step_tag = f'step_{i}'

            for j, (label, bg, fg) in enumerate(all_cells):
                cx = x + j * cell_w
                canvas.create_rectangle(cx, y, cx + cell_w - 1, y + _STEP_VIS_RECT_H - 1,
                                        fill=bg, outline=_Theme.Border, tags=step_tag)
                canvas.create_text(cx + cell_w // 2, y + _STEP_VIS_RECT_H // 2,
                                   text=label, font=('TkDefaultFont', 8), fill=fg,
                                   justify='center', tags=step_tag)

            self._step_canvas_regions.append((x, x + n_cols * cell_w))
            x += n_cols * cell_w + _STEP_VIS_STEP_GAP

        canvas.configure(scrollregion=(0, 0, x, canvas_h))

        if self._selected_step_idx is not None:
            self._highlight_selected_step_in_canvas(self._selected_step_idx)

    def _populate_hex_widget(
        self,
        widget: tk.Text,
        subevent: Optional[SubeventResults],
        step_ranges: List[tuple],
    ):
        widget.config(state=tk.NORMAL)
        widget.delete('1.0', tk.END)
        for tag in list(widget.tag_names()):
            if tag != 'sel':
                widget.tag_delete(tag)

        if subevent is None or subevent.raw_data is None:
            widget.insert('1.0', 'waiting for data...' if self.live_mode else 'no data')
            widget.config(state=tk.DISABLED)
            return

        raw = subevent.raw_data
        hex_rows = [
            ' '.join(f'{b:02x}' for b in raw[i:i + 16])
            for i in range(0, len(raw), 16)
        ]
        widget.insert('1.0', '\n'.join(hex_rows))

        widget.tag_configure('step_even', background=_Theme.AltBackground)
        widget.tag_configure('step_odd',  background=_Theme.Background)
        widget.tag_configure('step_selected', background=_Theme.Selection)
        widget.tag_raise('step_selected')

        for step_idx, (byte_start, byte_end) in enumerate(step_ranges):
            color_tag = 'step_even' if step_idx % 2 == 0 else 'step_odd'
            self._tag_bytes_in_widget(widget, color_tag, byte_start, byte_end)

        widget.config(state=tk.DISABLED)

    def _format_subevent_statistics(self, subevent: Optional[SubeventResults]) -> str:
        if subevent is None:
            return "waiting for data..." if self.live_mode else "none"

        steps = subevent.steps

        mode0_steps = [step for step in steps if step.mode == CSMode.MODE_0]
        total_num_mode0 = len(mode0_steps)
        num_aa_success = sum(
            1
            for step in mode0_steps
            if isinstance(step, CSStepMode0) and step.packet_quality == PacketQuality.AA_SUCCESS
        )
        num_aa_error = total_num_mode0 - num_aa_success

        mode2_steps = [step for step in steps if step.mode == CSMode.MODE_2]
        total_num_mode2 = len(mode2_steps)
        num_good = 0
        num_medium = 0
        num_low = 0

        for step in mode2_steps:
            if not isinstance(step, CSStepMode2):
                num_low += 1
                continue

            tones_quality = [tone.quality for tone in step.tones]

            if ToneQualityIndicator.TONE_QUALITY_HIGH in tones_quality:
                num_good += 1
            elif ToneQualityIndicator.TONE_QUALITY_MEDIUM in tones_quality:
                num_medium += 1
            elif ToneQualityIndicator.TONE_QUALITY_LOW in tones_quality:
                num_low += 1
            else:
                num_low += 1

        return (
            f"reference_power_level: {subevent.reference_power_level}, "
            f"num_steps_reported: {subevent.num_steps_reported}, "
            f"Mode-0 steps: {total_num_mode0} ({num_aa_success}/{num_aa_error}), "
            f"Mode-2 steps: {total_num_mode2} ({num_good}, {num_medium}, {num_low})"
        )

    def _update_stats_tab(self):
        self._set_text_widget(
            self.initiator_stats_text,
            self._format_subevent_statistics(self._current_initiator)
        )
        self._set_text_widget(
            self.reflector_stats_text,
            self._format_subevent_statistics(self._current_reflector)
        )
        self._ini_step_ranges = self._get_step_ranges(self._current_initiator)
        self._ref_step_ranges = self._get_step_ranges(self._current_reflector)
        self._selected_step_idx = None
        self._populate_hex_widget(self.ini_hex_text, self._current_initiator, self._ini_step_ranges)
        self._populate_hex_widget(self.ref_hex_text, self._current_reflector, self._ref_step_ranges)
        self._set_text_widget(self.step_details_text, 'Click on a step in the hex view to see details.')
        self._redraw_steps_canvas()
        if self._ini_step_ranges or self._ref_step_ranges:
            self._select_step(0)
