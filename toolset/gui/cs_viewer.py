import tkinter as tk
from tkinter import ttk
import math
import numpy as np
from typing import List, Optional, Callable, Dict
from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.cs_utils.cs_step import (
    CSMode,
    CSStepMode0,
    CSStepMode2,
    PacketQuality,
    ToneQualityIndicator,
    ToneQualityIndicatorExtensionSlot,
)
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch
from toolset.gui.cs_theme import _ThemeColors, LIGHT_THEME, DARK_THEME

# Active theme - set by CSViewer.__init__ based on --dark / --light CLI flag.
_Theme: _ThemeColors = DARK_THEME


_STEP_VIS_CELL_W = 34    # width for a single-packet rect (modes 0, 1, 3)
_STEP_VIS_TONE_W = 20    # width per tone rect (mode 2)
_STEP_VIS_RECT_H = 28    # row height
_STEP_VIS_STEP_GAP = 6   # horizontal gap between consecutive step groups
_STEP_VIS_PAD_X = 8      # left/right canvas padding
_STEP_VIS_PAD_Y = 5      # top/bottom canvas padding


class CSViewer:
    """GUI for viewing Channel Sounding data"""

    def __init__(self, initiator_subevents: List = None, reflector_subevents: List = None, dark_mode: bool = True):
        self.initiator_subevents = initiator_subevents or []
        self.reflector_subevents = reflector_subevents or []

        self.initiator_map = {se.procedure_counter: se for se in self.initiator_subevents if se is not None}
        self.reflector_map = {se.procedure_counter: se for se in self.reflector_subevents if se is not None}

        self.phase_slope_map: Dict[int, Dict[int, float]] = {}
        self.rssi_ini_map: Dict[int, Dict[int, float]] = {}
        self.rssi_ref_map: Dict[int, Dict[int, float]] = {}

        self.live_mode = True
        self.live_initiator: Optional[SubeventResults] = None
        self.live_reflector: Optional[SubeventResults] = None
        self.live_phase_slope: Optional[Dict[int, float]] = None
        self.live_rssi_ini: Optional[Dict[int, float]] = None
        self.live_rssi_ref: Optional[Dict[int, float]] = None
        self.gui_refresh_interval_ms = 100
        self._live_render_scheduled = False
        self._pending_live_counter: Optional[int] = None
        self._current_initiator: Optional[SubeventResults] = None
        self._current_reflector: Optional[SubeventResults] = None
        self._current_phase_slope_data: Optional[Dict[int, float]] = None
        self._current_rssi_ini_data: Optional[Dict[int, float]] = None
        self._current_rssi_ref_data: Optional[Dict[int, float]] = None
        self._tab_update_handlers: Dict[str, Callable[[], None]] = {}
        self._tab_indices: Dict[str, int] = {}
        self._active_tab_key: Optional[str] = None
        self._phase_channels: tuple[int, ...] = ()
        self._rssi_ini_channels: tuple[int, ...] = ()
        self._rssi_ref_channels: tuple[int, ...] = ()
        self._phase_collection: Optional[PolyCollection] = None
        self._rssi_ini_collection: Optional[PolyCollection] = None
        self._rssi_ref_collection: Optional[PolyCollection] = None
        self._blit_background = None
        self._force_full_redraw = True
        self._bg_refresh_pending = False
        self._phase_ylim = (-1.0, 1.0)
        self._rssi_ylim = (-1.0, 1.0)
        self._rssi_bottom_dbm = -100.0
        self._rssi_top_dbm = 0.0
        self._bar_width = 0.35

        # Subevent steps-tab hex view state
        self._selected_step_idx: Optional[int] = None
        self._ini_step_ranges: List[tuple] = []
        self._ref_step_ranges: List[tuple] = []
        self._step_canvas_regions: List[tuple] = []  # (x1, x2) per step group

        all_counters = sorted(set(self.initiator_map.keys()) | set(self.reflector_map.keys()))

        global _Theme
        _Theme = DARK_THEME if dark_mode else LIGHT_THEME

        self.root = tk.Tk()
        self.root.title("Channel Sounding Viewer")
        self.root.geometry("1760x900")
        self._apply_ttk_theme()

        self._create_widgets(all_counters)

    def _apply_ttk_theme(self):
        """Configure ttk styles to match the active theme."""
        style = ttk.Style(self.root)
        bg = _Theme.Background
        fg = _Theme.Foreground
        alt_bg = _Theme.AltBackground
        border = _Theme.Border

        if _Theme is DARK_THEME:
            style.theme_use('clam')

        # In dark mode suppress clam's built-in 3-D highlight/shadow by pinning
        # lightcolor/darkcolor to the same value as the background.
        relief_hi = alt_bg if _Theme is DARK_THEME else bg
        relief_lo = bg    if _Theme is DARK_THEME else border
        arrow_color = _Theme.SubtleForeground if _Theme is DARK_THEME else fg

        style.configure('.', background=bg, foreground=fg, bordercolor=border,
                        lightcolor=relief_hi, darkcolor=relief_lo,
                        troughcolor=alt_bg, selectbackground=_Theme.Selection,
                        selectforeground=fg)
        style.configure('TFrame', background=bg)
        style.configure('TLabel', background=bg, foreground=fg)
        style.configure('TCheckbutton', background=bg, foreground=fg,
                        bordercolor=border, lightcolor=relief_hi, darkcolor=relief_lo)
        style.map('TCheckbutton',
                  background=[('active', border)],
                  indicatorcolor=[('selected', _Theme.SelectionBorder), ('!selected', alt_bg)])
        style.configure('TNotebook', background=bg, bordercolor=border,
                        lightcolor=relief_hi, darkcolor=relief_lo)
        style.configure('TNotebook.Tab', background=alt_bg, foreground=fg, padding=[10, 4],
                        bordercolor=border, lightcolor=relief_hi, darkcolor=relief_lo)
        style.map('TNotebook.Tab',
                  background=[('selected', bg)],
                  foreground=[('selected', fg)],
                  expand=[('selected', [1, 1, 1, 0])])
        style.configure('TScrollbar', background=alt_bg, troughcolor=bg,
                        arrowcolor=arrow_color, bordercolor=border,
                        lightcolor=relief_hi, darkcolor=relief_lo, gripcount=0)
        style.map('TScrollbar', background=[('active', border), ('!active', alt_bg)])
        style.configure('TSpinbox', fieldbackground=alt_bg, background=alt_bg,
                        foreground=fg, arrowcolor=arrow_color, bordercolor=border,
                        lightcolor=relief_hi, darkcolor=relief_lo,
                        insertcolor=fg, selectbackground=_Theme.Selection,
                        selectforeground=fg)
        self.root.configure(bg=bg)

    def _create_widgets(self, procedure_counters: List[int]):
        """Create GUI widgets"""

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.live_var = tk.BooleanVar(value=True)
        live_checkbox = ttk.Checkbutton(
            main_frame,
            text="Live",
            variable=self.live_var,
            command=self._on_live_toggled
        )
        live_checkbox.grid(row=0, column=0, sticky=tk.W, pady=5)

        ttk.Label(main_frame, text="Procedure Counter:").grid(row=0, column=1, sticky=tk.W, pady=5, padx=(20, 0))

        self.counter_var = tk.IntVar(value=procedure_counters[0] if procedure_counters else 0)
        self.all_procedure_counters = procedure_counters if procedure_counters else [0]

        self.counter_spinbox = ttk.Spinbox(
            main_frame,
            from_=min(procedure_counters) if procedure_counters else 0,
            to=max(procedure_counters) if procedure_counters else 0,
            textvariable=self.counter_var,
            width=15,
            command=self._on_counter_changed
        )
        self.counter_spinbox.grid(row=0, column=2, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        self.counter_spinbox.bind('<Return>', self._on_counter_enter)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        self._create_tabs()
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        self._active_tab_key = self._tab_key_from_index(self.notebook.index('current'))
        self._update_display()

    def _create_tabs(self):
        self._register_tab('stats', 'Subevent steps', self._build_stats_tab, self._update_stats_tab)
        self._register_tab('plots', 'RSSI and phase slope', self._build_plots_tab, self._update_plots_tab)

    def _register_tab(
        self,
        key: str,
        title: str,
        build_tab_content: Callable[[ttk.Frame], None],
        update_tab_content: Callable[[], None],
    ):
        frame = ttk.Frame(self.notebook, padding='12')
        self.notebook.add(frame, text=title)
        build_tab_content(frame)
        self._tab_update_handlers[key] = update_tab_content
        self._tab_indices[key] = self.notebook.index('end') - 1

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

    def _get_step_ranges(self, subevent: Optional[SubeventResults]) -> List[tuple]:
        if subevent is None or subevent.step_byte_ranges is None:
            return []
        return subevent.step_byte_ranges

    def _get_step_cells(self, step, role: str) -> List[tuple]:
        """Return list of (label, bg_color, text_color) cells for one side of a step."""
        if step is None:
            return [(role, _Theme.StepMissingBackground, _Theme.StepMissingForeground)]

        mode_num = step.mode.value

        if isinstance(step, CSStepMode0):
            if step.packet_quality == PacketQuality.AA_SUCCESS:
                bg, fg = _Theme.StepGoodBackground, _Theme.StepGoodForeground
            else:
                bg, fg = _Theme.StepBadBackground, _Theme.StepBadForeground
            return [(f'{role}\n{mode_num}', bg, fg)]

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
                cells.append((f'{role}\n{mode_num}', color, fg))
            return cells or [(f'{role}\n{mode_num}', _Theme.StepDefaultBackground, _Theme.StepDefaultForeground)]

        # Mode 1, 3, or unrecognised
        return [(f'{role}\n{mode_num}', _Theme.StepDefaultBackground, _Theme.StepDefaultForeground)]

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

    def _on_steps_canvas_click(self, event):
        canvas_x = self.steps_canvas.canvasx(event.x)
        step_idx = next(
            (i for i, (x1, x2) in enumerate(self._step_canvas_regions) if x1 <= canvas_x < x2),
            None,
        )
        if step_idx is not None:
            self._select_step(step_idx)
            self.steps_canvas.focus_set()

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

    def _bind_nav_keys(self, widget: tk.BaseWidget):
        widget.bind('<Left>',  lambda e: (self._on_hex_key_navigate(-1), 'break')[1])
        widget.bind('<Right>', lambda e: (self._on_hex_key_navigate(+1), 'break')[1])
        widget.bind('<Up>',    lambda e: (self._on_hex_key_navigate(-2), 'break')[1])
        widget.bind('<Down>',  lambda e: (self._on_hex_key_navigate(+2), 'break')[1])

    def _on_hex_key_navigate(self, delta: int):
        max_step = max(len(self._ini_step_ranges), len(self._ref_step_ranges)) - 1
        if max_step < 0:
            return
        current = self._selected_step_idx if self._selected_step_idx is not None else 0
        new_idx = max(0, min(max_step, current + delta))
        if new_idx != self._selected_step_idx:
            self._select_step(new_idx)

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

    def _apply_plot_theme(self):
        """Apply the current theme colors to the matplotlib figure and axes."""
        self.fig.patch.set_facecolor(_Theme.PlotBackground)
        for ax in (self.ax_phase, self.ax_rssi):
            ax.set_facecolor(_Theme.PlotBackground)
            ax.tick_params(colors=_Theme.PlotForeground, which='both')
            ax.xaxis.label.set_color(_Theme.PlotForeground)
            ax.yaxis.label.set_color(_Theme.PlotForeground)
            ax.title.set_color(_Theme.PlotForeground)
            for spine in ax.spines.values():
                spine.set_edgecolor(_Theme.Border)
            ax.grid(True, color=_Theme.PlotGridColor)

    def _build_plots_tab(self, tab_frame: ttk.Frame):
        self.fig = Figure(figsize=(8, 8), dpi=100)
        self.ax_phase = self.fig.add_subplot(211)
        self.ax_phase.set_xlabel('Channel Index')
        self.ax_phase.set_ylabel('Sum of Phases')
        self.ax_phase.set_title('Phase Slope')

        self.ax_rssi = self.fig.add_subplot(212)
        self.ax_rssi.set_xlabel('Channel Index')
        self.ax_rssi.set_ylabel('RSSI Magnitude, dBm')
        self.ax_rssi.set_title('RSSI Values')

        self._apply_plot_theme()
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=tab_frame)
        tk_widget = self.canvas.get_tk_widget()
        tk_widget.configure(bg=_Theme.PlotBackground)
        tk_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self._initialize_plot_artists()
        self.canvas.mpl_connect('draw_event', self._on_canvas_draw)

        tab_frame.rowconfigure(0, weight=1)
        tab_frame.columnconfigure(0, weight=1)

    def _tab_key_from_index(self, tab_index: int) -> Optional[str]:
        for key, index in self._tab_indices.items():
            if index == tab_index:
                return key
        return None

    def _on_tab_changed(self, _event):
        self._active_tab_key = self._tab_key_from_index(self.notebook.index('current'))
        self._update_current_tab_content()

    def _initialize_plot_artists(self):
        self._phase_collection = PolyCollection([], facecolors=[_Theme.PlotPhaseBarColor],
                                                edgecolors=['none'], antialiaseds=False, animated=True)
        self.ax_phase.add_collection(self._phase_collection)
        self._rssi_ini_collection = PolyCollection([], facecolors=[_Theme.PlotIniBarColor],
                                                   edgecolors=['none'], antialiaseds=False, alpha=0.8, animated=True)
        self.ax_rssi.add_collection(self._rssi_ini_collection)
        self._rssi_ref_collection = PolyCollection([], facecolors=[_Theme.PlotRefBarColor],
                                                   edgecolors=['none'], antialiaseds=False, alpha=0.8, animated=True)
        self.ax_rssi.add_collection(self._rssi_ref_collection)
        self._update_rssi_legend()
        self._force_full_redraw = True

    def _update_rssi_legend(self):
        handles = [
            Patch(facecolor=_Theme.PlotIniBarColor, edgecolor=_Theme.PlotIniBarColor,
                  alpha=0.8, label='Initiator'),
            Patch(facecolor=_Theme.PlotRefBarColor, edgecolor=_Theme.PlotRefBarColor,
                  alpha=0.8, label='Reflector'),
        ]
        legend = self.ax_rssi.legend(handles=handles)
        legend.get_frame().set_facecolor(_Theme.PlotBackground)
        legend.get_frame().set_edgecolor(_Theme.Border)
        for text, color in zip(legend.get_texts(), (_Theme.PlotIniBarColor, _Theme.PlotRefBarColor)):
            text.set_color(color)

    def _on_canvas_draw(self, _event):
        if not self._supports_blit():
            return
        self._blit_background = self.canvas.copy_from_bbox(self.fig.bbox)
        self._force_full_redraw = False

    def _supports_blit(self) -> bool:
        return hasattr(self.canvas, 'copy_from_bbox')

    def _on_live_toggled(self):
        """Handle live mode checkbox toggle"""
        self.live_mode = self.live_var.get()
        self._update_display()

    def _on_counter_enter(self, _event=None):
        """Handle Enter key press in the counter spinbox."""
        try:
            value = int(self.counter_spinbox.get())
            lo = int(float(self.counter_spinbox.cget('from')))
            hi = int(float(self.counter_spinbox.cget('to')))
            value = max(lo, min(hi, value))
            self.counter_var.set(value)
        except (ValueError, tk.TclError):
            pass
        self._on_counter_changed()

    def _on_counter_changed(self):
        """Handle spinbox counter change."""
        if self.live_mode:
            self.live_mode = False
            self.live_var.set(False)
        self._update_display()

    def _update_display(self):
        """Update display based on current mode"""
        try:
            counter_value = self.counter_var.get()

            if self.live_mode:
                self._current_initiator = self.live_initiator
                self._current_reflector = self.live_reflector
                self._current_phase_slope_data = self.live_phase_slope
                self._current_rssi_ini_data = self.live_rssi_ini
                self._current_rssi_ref_data = self.live_rssi_ref
            else:
                self._current_initiator = self.initiator_map.get(counter_value)
                self._current_reflector = self.reflector_map.get(counter_value)
                self._current_phase_slope_data = self.phase_slope_map.get(counter_value)
                self._current_rssi_ini_data = self.rssi_ini_map.get(counter_value)
                self._current_rssi_ref_data = self.rssi_ref_map.get(counter_value)

            self._update_current_tab_content()

        except Exception as e:
            print(f"[ERROR] Exception in _update_display: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    def _update_current_tab_content(self):
        if self._active_tab_key is None:
            self._active_tab_key = self._tab_key_from_index(self.notebook.index('current'))
        if self._active_tab_key is None:
            return

        update_handler = self._tab_update_handlers.get(self._active_tab_key)
        if update_handler is not None:
            update_handler()

    def _update_plots_tab(self):
        self._update_phase_plot(self._current_phase_slope_data)
        self._update_rssi_plot(self._current_rssi_ini_data, self._current_rssi_ref_data)
        self._render_plots()

    def update_live_data(self, initiator: SubeventResults, reflector: SubeventResults, phase_slope_data: Dict[int, float], rssi_data_ini: Dict[int, float], rssi_data_ref: Dict[int, float]):
        """Update live data from consumer thread - thread-safe"""
        def _update():
            self.live_initiator = initiator
            self.live_reflector = reflector
            self.live_phase_slope = phase_slope_data
            self.live_rssi_ini = rssi_data_ini
            self.live_rssi_ref = rssi_data_ref

            self.initiator_map[initiator.procedure_counter] = initiator
            self.reflector_map[reflector.procedure_counter] = reflector
            self.phase_slope_map[initiator.procedure_counter] = phase_slope_data
            self.rssi_ini_map[initiator.procedure_counter] = rssi_data_ini
            self.rssi_ref_map[initiator.procedure_counter] = rssi_data_ref

            all_counters = sorted(set(self.initiator_map.keys()) | set(self.reflector_map.keys()))
            if all_counters:
                self.counter_spinbox.config(from_=min(all_counters), to=max(all_counters))

            if self.live_mode:
                self._pending_live_counter = initiator.procedure_counter
                if not self._live_render_scheduled:
                    self._live_render_scheduled = True
                    self.root.after(self.gui_refresh_interval_ms, self._flush_live_render)

        self.root.after(0, _update)

    def _flush_live_render(self):
        """Render latest live data at most once per refresh interval."""
        self._live_render_scheduled = False

        if not self.live_mode:
            return

        counter = self._pending_live_counter
        if counter is None:
            return

        self.counter_var.set(counter)
        self._update_display()

    def _set_text_widget(self, widget: tk.Text, value: str):
        widget.config(state=tk.NORMAL)
        widget.delete('1.0', tk.END)
        widget.insert(tk.END, value)
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

    @staticmethod
    def _bar_verts(positions, heights, width, bottom=0.0):
        n = len(positions)
        if n == 0:
            return np.empty((0, 4, 2))
        hw = width / 2
        x = np.asarray(positions, dtype=np.float64)
        h = np.asarray(heights, dtype=np.float64)
        verts = np.empty((n, 4, 2), dtype=np.float64)
        verts[:, 0, 0] = x - hw;  verts[:, 0, 1] = bottom
        verts[:, 1, 0] = x - hw;  verts[:, 1, 1] = bottom + h
        verts[:, 2, 0] = x + hw;  verts[:, 2, 1] = bottom + h
        verts[:, 3, 0] = x + hw;  verts[:, 3, 1] = bottom
        return verts

    def _update_phase_plot(self, phase_slope_data: Optional[Dict[int, float]]):
        """Update the phase slope plot"""
        if phase_slope_data and len(phase_slope_data) > 0:
            sorted_channels = tuple(sorted(phase_slope_data.keys()))
            phases = [phase_slope_data[ch] for ch in sorted_channels]
            offset = phases[0]
            phases = [v - offset for v in phases]
        else:
            sorted_channels = ()
            phases = []

        if sorted_channels != self._phase_channels:
            self._phase_channels = sorted_channels
            self._force_full_redraw = True

        self._phase_collection.set_verts(self._bar_verts(sorted_channels, phases, 0.6))
        self._update_phase_limits(sorted_channels, phases)

    def _rssi_plot_bounds(self, values: List[float]) -> tuple[int, int]:
        if not values:
            return -100, 0

        bottom = math.floor(min(values) / 10) * 10
        top = math.ceil(max(values) / 10) * 10

        return bottom, top

    def _update_rssi_plot(self, rssi_ini_data: Optional[Dict[int, float]], rssi_ref_data: Optional[Dict[int, float]]):
        """Update the RSSI plot"""
        ini_channels = tuple(sorted(rssi_ini_data.keys())) if rssi_ini_data else ()
        ref_channels = tuple(sorted(rssi_ref_data.keys())) if rssi_ref_data else ()
        ini_values = [rssi_ini_data[ch] for ch in ini_channels] if rssi_ini_data else []
        ref_values = [rssi_ref_data[ch] for ch in ref_channels] if rssi_ref_data else []
        all_values = [*ini_values, *ref_values]
        self._rssi_bottom_dbm, self._rssi_top_dbm = self._rssi_plot_bounds(all_values)
        bar_bottom = min(self._rssi_bottom_dbm, self._rssi_ylim[0])
        ini_heights = [value - bar_bottom for value in ini_values]
        ref_heights = [value - bar_bottom for value in ref_values]

        if ini_channels != self._rssi_ini_channels:
            self._rssi_ini_channels = ini_channels
            self._force_full_redraw = True

        if ref_channels != self._rssi_ref_channels:
            self._rssi_ref_channels = ref_channels
            self._force_full_redraw = True

        ini_positions = [ch - self._bar_width / 2 for ch in ini_channels]
        ref_positions = [ch + self._bar_width / 2 for ch in ref_channels]
        self._rssi_ini_collection.set_verts(self._bar_verts(ini_positions, ini_heights, self._bar_width, bar_bottom))
        self._rssi_ref_collection.set_verts(self._bar_verts(ref_positions, ref_heights, self._bar_width, bar_bottom))

        self._update_rssi_limits(ini_channels, ref_channels, self._rssi_bottom_dbm, self._rssi_top_dbm)

    def _update_phase_limits(self, channels: tuple[int, ...], values: List[float]):
        if channels:
            x_min = min(channels) - 0.8
            x_max = max(channels) + 0.8
            min_value = min(values) if values else -1.0
            max_value = max(values) if values else 1.0
            y_pad = max(0.5, (max_value - min_value) * 0.1)
            y_min = min(min_value - y_pad, 0.0)
            y_max = max(max_value + y_pad, 0.0)
            if y_min == y_max:
                y_min -= 1.0
                y_max += 1.0
            # Round to nearest 1.0 so small data changes don't force a full redraw
            y_min = math.floor(y_min)
            y_max = math.ceil(y_max)
        else:
            x_min, x_max = -1.0, 1.0
            y_min, y_max = -1.0, 1.0

        new_ylim = (y_min, y_max)
        if self.ax_phase.get_xlim() != (x_min, x_max):
            self.ax_phase.set_xlim(x_min, x_max)
            self._force_full_redraw = True
        if self._phase_ylim != new_ylim:
            self.ax_phase.set_ylim(*new_ylim)
            self._phase_ylim = new_ylim
            self._force_full_redraw = True

    def _update_rssi_limits(
        self,
        ini_channels: tuple[int, ...],
        ref_channels: tuple[int, ...],
        y_bottom: float,
        y_top: float,
    ):
        channels = [*ini_channels, *ref_channels]
        if channels:
            x_min = min(channels) - 0.8
            x_max = max(channels) + 0.8
            y_min, y_max = y_bottom, y_top
        else:
            x_min, x_max = -1.0, 1.0
            y_min, y_max = -50.0, -40.0

        new_ylim = (y_min, y_max)
        if self.ax_rssi.get_xlim() != (x_min, x_max):
            self.ax_rssi.set_xlim(x_min, x_max)
            self._force_full_redraw = True
        if self._rssi_ylim != new_ylim:
            self.ax_rssi.set_ylim(*new_ylim)
            self._rssi_ylim = new_ylim
            self._force_full_redraw = True

    def _render_plots(self):
        def _draw_bar_artists():
            if self._phase_collection is not None:
                self.ax_phase.draw_artist(self._phase_collection)
            if self._rssi_ini_collection is not None:
                self.ax_rssi.draw_artist(self._rssi_ini_collection)
            if self._rssi_ref_collection is not None:
                self.ax_rssi.draw_artist(self._rssi_ref_collection)

        blit_ready = (
            self._supports_blit()
            and self._blit_background is not None
        )

        if not blit_ready:
            # First render ever - must do synchronous full draw
            self.canvas.draw()
            self._force_full_redraw = False
            if self._blit_background is not None:
                self.canvas.restore_region(self._blit_background)
                _draw_bar_artists()
                self.canvas.blit(self.fig.bbox)
        else:
            # Fast path: always blit bars on existing background
            self.canvas.restore_region(self._blit_background)
            _draw_bar_artists()
            self.canvas.blit(self.fig.bbox)
            # If axes limits changed, schedule deferred background refresh
            if self._force_full_redraw and not self._bg_refresh_pending:
                self._bg_refresh_pending = True
                self.root.after_idle(self._deferred_bg_refresh)

    def _deferred_bg_refresh(self):
        """Redraw axes/ticks/grid in the background, then re-blit bar artists."""
        self._bg_refresh_pending = False
        self._force_full_redraw = False
        self.canvas.draw()
        if self._blit_background is not None:
            self.canvas.restore_region(self._blit_background)
            if self._phase_collection is not None:
                self.ax_phase.draw_artist(self._phase_collection)
            if self._rssi_ini_collection is not None:
                self.ax_rssi.draw_artist(self._rssi_ini_collection)
            if self._rssi_ref_collection is not None:
                self.ax_rssi.draw_artist(self._rssi_ref_collection)
            self.canvas.blit(self.fig.bbox)

    def run(self):
        """Start the GUI event loop"""
        self.root.mainloop()


def launch_viewer(initiator_subevents: List = None, reflector_subevents: List = None, dark_mode: bool = True):
    """Launch the CS Viewer GUI"""
    viewer = CSViewer(initiator_subevents, reflector_subevents, dark_mode=dark_mode)
    return viewer
