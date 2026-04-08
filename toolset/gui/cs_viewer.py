import tkinter as tk
from tkinter import ttk
from typing import List, Optional, Callable, Dict
from toolset.cs_utils.cs_subevent import SubeventResults
from toolset.gui.cs_theme import _Theme, LIGHT_THEME, DARK_THEME
from toolset.gui.setup_tab import SetupTabMixin
from toolset.gui.steps_tab import StepsTabMixin
from toolset.gui.plots_tab import PlotsTabMixin
from toolset.gui.ifft_tab import IFftTabMixin
from toolset.gui.music_tab import MusicTabMixin
from toolset.gui.sensing_tab import SensingTabMixin
from toolset.gui.gesture_tab import GestureTabMixin
from matplotlib.collections import PolyCollection

# Skip a render when this many subevents have accumulated since the last rendered
# one. Prevents back-to-back renders (which starve the mainloop) when a slow
# tab (e.g. MUSIC eigendecomposition) takes longer than gui_refresh_interval_ms.
_LAG_SKIP_COUNT = 3


class CSViewer(SetupTabMixin, StepsTabMixin, PlotsTabMixin, IFftTabMixin, MusicTabMixin, SensingTabMixin, GestureTabMixin):
    """GUI for viewing Channel Sounding data"""

    def __init__(self, initiator_subevents: List = None, reflector_subevents: List = None, dark_mode: bool = True, ml: bool = False, on_close: Callable = None):
        self.initiator_subevents = initiator_subevents or []
        self.reflector_subevents = reflector_subevents or []

        self.initiator_map = {se.procedure_counter: se for se in self.initiator_subevents if se is not None}
        self.reflector_map = {se.procedure_counter: se for se in self.reflector_subevents if se is not None}

        self.phase_slope_map: Dict[int, Dict[int, float]] = {}
        self.amplitude_response_map: Dict[int, Dict[int, float]] = {}

        self.live_mode = True
        self.live_initiator: Optional[SubeventResults] = None
        self.live_reflector: Optional[SubeventResults] = None
        self.live_phase_slope: Optional[Dict[int, float]] = None
        self.live_amplitude_response: Optional[Dict[int, float]] = None
        self.gui_refresh_interval_ms = 100
        self._live_render_scheduled = False
        self._pending_live_counter: Optional[int] = None
        self._last_rendered_counter: Optional[int] = None
        self._current_counter: Optional[int] = None
        self._current_initiator: Optional[SubeventResults] = None
        self._current_reflector: Optional[SubeventResults] = None
        self._current_phase_slope_data: Optional[Dict[int, float]] = None
        self._current_amplitude_response_data: Optional[Dict[int, float]] = None
        self._tab_update_handlers: Dict[str, Callable[[], None]] = {}
        self._tab_indices: Dict[str, int] = {}
        self._active_tab_key: Optional[str] = None
        self._phase_channels: tuple[int, ...] = ()
        self._amplitude_response_channels: tuple[int, ...] = ()
        self._phase_collection: Optional[PolyCollection] = None
        self._amplitude_response_collection: Optional[PolyCollection] = None
        self._distance_text = None
        self._blit_background = None
        self._force_full_redraw = True
        self._bg_refresh_pending = False
        self._phase_ylim = (-1.0, 1.0)
        self._rssi_ylim = (-1.0, 1.0)
        self._rssi_bottom_dbm = -100.0
        self._rssi_top_dbm = 0.0
        self._bar_width = 0.35

        # Capabilities description state
        self._capabilities_labels: List[str] = []
        self._selected_capability_line: Optional[int] = None

        # Subevent steps-tab hex view state
        self._selected_step_idx: Optional[int] = None
        self._ini_step_ranges: List[tuple] = []
        self._ref_step_ranges: List[tuple] = []
        self._step_canvas_regions: List[tuple] = []  # (x1, x2) per step group

        all_counters = sorted(set(self.initiator_map.keys()) | set(self.reflector_map.keys()))

        self._ml_enabled = ml
        self._on_close_callback = on_close
        _Theme.set(DARK_THEME if dark_mode else LIGHT_THEME)

        self.root = tk.Tk()
        self.root.title("Channel Sounding Viewer")
        self.root.geometry("1760x900")
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)
        self._apply_ttk_theme()

        self._create_widgets(all_counters)

    def _apply_ttk_theme(self):
        """Configure ttk styles to match the active theme."""
        style = ttk.Style(self.root)
        bg = _Theme.Background
        fg = _Theme.Foreground
        alt_bg = _Theme.AltBackground
        border = _Theme.Border

        if _Theme._current is DARK_THEME:
            style.theme_use('clam')

        # In dark mode suppress clam's built-in 3-D highlight/shadow by pinning
        # lightcolor/darkcolor to the same value as the background.
        relief_hi = alt_bg if _Theme._current is DARK_THEME else bg
        relief_lo = bg    if _Theme._current is DARK_THEME else border
        arrow_color = _Theme.SubtleForeground if _Theme._current is DARK_THEME else fg

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
        self._register_tab('setup', 'CS setup', self._build_setup_tab, self._update_setup_tab)
        self._register_tab('stats', 'Subevent steps', self._build_stats_tab, self._update_stats_tab)
        self._register_tab('plots', 'Amplitude response and phase slope', self._build_plots_tab, self._update_plots_tab)
        self._register_tab('ifft', 'IFFT', self._build_ifft_tab, self._update_ifft_tab)
        self._register_tab('music', 'MUSIC', self._build_music_tab, self._update_music_tab)
        if self._ml_enabled:
            self._register_tab('sensing', 'Sensing', self._build_sensing_tab, self._update_sensing_tab)
            self._register_tab('gesture', 'Gesture', self._build_gesture_tab, self._update_gesture_tab)

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

    def _tab_key_from_index(self, tab_index: int) -> Optional[str]:
        for key, index in self._tab_indices.items():
            if index == tab_index:
                return key
        return None

    def _on_tab_changed(self, _event):
        self._active_tab_key = self._tab_key_from_index(self.notebook.index('current'))
        self._update_current_tab_content()

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
                self._current_counter = counter_value
                self._current_initiator = self.live_initiator
                self._current_reflector = self.live_reflector
                self._current_phase_slope_data = self.live_phase_slope
                self._current_amplitude_response_data = self.live_amplitude_response
            else:
                self._current_counter = counter_value
                self._current_initiator = self.initiator_map.get(counter_value)
                self._current_reflector = self.reflector_map.get(counter_value)
                self._current_phase_slope_data = self.phase_slope_map.get(counter_value)
                self._current_amplitude_response_data = self.amplitude_response_map.get(counter_value)

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

    def update_live_data(self, initiator: SubeventResults, reflector: SubeventResults, phase_slope_data: Dict[int, float], amplitude_response_data: Dict[int, float]):
        """Update live data from consumer thread - thread-safe"""
        def _update():
            self.live_initiator = initiator
            self.live_reflector = reflector
            self.live_phase_slope = phase_slope_data
            self.live_amplitude_response = amplitude_response_data

            self.initiator_map[initiator.procedure_counter] = initiator
            self.reflector_map[reflector.procedure_counter] = reflector
            self.phase_slope_map[initiator.procedure_counter] = phase_slope_data
            self.amplitude_response_map[initiator.procedure_counter] = amplitude_response_data

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
        """Render latest live data at most once per refresh interval.
        Skips render when more than _LAG_SKIP_COUNT subevents have accumulated
        to avoid back-to-back renders that block the mainloop."""
        self._live_render_scheduled = False

        if not self.live_mode:
            return

        counter = self._pending_live_counter
        if counter is None:
            return

        lag = (counter - self._last_rendered_counter) if self._last_rendered_counter is not None else 0
        if lag > _LAG_SKIP_COUNT:
            # Too many subevents queued up. Advance the reference so the next
            # flush renders the latest data instead of an already-stale frame.
            self._last_rendered_counter = counter
            self._live_render_scheduled = True
            self.root.after(self.gui_refresh_interval_ms, self._flush_live_render)
            print(f"GUI dropped {lag} frames to catch up with live data (counter={counter})")
            return

        self._last_rendered_counter = counter
        self.counter_var.set(counter)
        self._update_display()

    def _set_text_widget(self, widget: tk.Text, value: str):
        widget.config(state=tk.NORMAL)
        widget.delete('1.0', tk.END)
        widget.insert(tk.END, value)
        widget.config(state=tk.DISABLED)

    def _handle_close(self):
        """Called when the window's close button is pressed."""
        if self._on_close_callback:
            self._on_close_callback()
        self.root.destroy()

    def run(self):
        """Start the GUI event loop"""
        self.root.mainloop()


def launch_viewer(initiator_subevents: List = None, reflector_subevents: List = None, dark_mode: bool = True, ml: bool = False, on_close: Callable = None):
    """Launch the CS Viewer GUI"""
    viewer = CSViewer(initiator_subevents, reflector_subevents, dark_mode=dark_mode, ml=ml, on_close=on_close)
    return viewer
