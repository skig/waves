import tkinter as tk
from tkinter import ttk
from typing import List, Optional, Callable
from toolset.cs_utils.cs_subevent import SubeventResults


class CSViewer:
    """GUI for viewing Channel Sounding data"""

    def __init__(self, initiator_subevents: List = None, reflector_subevents: List = None):
        self.initiator_subevents = initiator_subevents or []
        self.reflector_subevents = reflector_subevents or []

        # Create dictionaries for quick lookup by procedure_counter (filter out None values)
        self.initiator_map = {se.procedure_counter: se for se in self.initiator_subevents if se is not None}
        self.reflector_map = {se.procedure_counter: se for se in self.reflector_subevents if se is not None}

        # Live mode state
        self.live_mode = False
        self.live_initiator: Optional[SubeventResults] = None
        self.live_reflector: Optional[SubeventResults] = None
        self._all_counters_cache = set()  # Track known counters to avoid redundant updates

        # Get all unique procedure counters
        all_counters = sorted(set(self.initiator_map.keys()) | set(self.reflector_map.keys()))

        # Create main window
        self.root = tk.Tk()
        self.root.title("Channel Sounding Viewer")
        self.root.geometry("900x600")

        # Create UI elements
        self._create_widgets(all_counters)

    def _create_widgets(self, procedure_counters: List[int]):
        """Create GUI widgets"""

        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Live mode checkbox
        self.live_var = tk.BooleanVar(value=False)
        live_checkbox = ttk.Checkbutton(
            main_frame,
            text="Live",
            variable=self.live_var,
            command=self._on_live_toggled
        )
        live_checkbox.grid(row=0, column=0, sticky=tk.W, pady=5)

        # Procedure counter selection
        ttk.Label(main_frame, text="Procedure Counter:").grid(row=0, column=1, sticky=tk.W, pady=5, padx=(20, 0))

        self.counter_var = tk.IntVar(value=procedure_counters[0] if procedure_counters else 0)
        self.all_procedure_counters = procedure_counters if procedure_counters else [0]

        # Spinbox for counter selection
        self.counter_spinbox = ttk.Spinbox(
            main_frame,
            from_=min(procedure_counters) if procedure_counters else 0,
            to=max(procedure_counters) if procedure_counters else 0,
            textvariable=self.counter_var,
            width=15,
            command=self._on_counter_changed
        )
        self.counter_spinbox.grid(row=0, column=2, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)

        # Initiator steps display
        ttk.Label(main_frame, text="Initiator Steps:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.initiator_steps_label = ttk.Label(main_frame, text="")
        self.initiator_steps_label.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(10, 0))

        # Reflector steps display
        ttk.Label(main_frame, text="Reflector Steps:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.reflector_steps_label = ttk.Label(main_frame, text="")
        self.reflector_steps_label.grid(row=3, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(10, 0))

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)

        # Initial update
        self._update_display()

    def _on_live_toggled(self):
        """Handle live mode checkbox toggle"""
        self.live_mode = self.live_var.get()
        self._update_display()

    def _on_counter_changed(self):
        """Handle spinbox counter change."""
        self._update_display()

    def _update_display(self):
        """Update display based on current mode"""
        try:
            counter_value = self.counter_var.get()

            if self.live_mode:
                # Show live data
                if self.live_initiator:
                    info = self._get_subevent_info(self.live_initiator)
                    self.initiator_steps_label.config(text=info)
                else:
                    self.initiator_steps_label.config(text="waiting for data...")

                if self.live_reflector:
                    info = self._get_subevent_info(self.live_reflector)
                    self.reflector_steps_label.config(text=info)
                else:
                    self.reflector_steps_label.config(text="waiting for data...")
            else:
                # Show historical data by counter
                if counter_value in self.initiator_map:
                    info = self._get_subevent_info(self.initiator_map[counter_value])
                    self.initiator_steps_label.config(text=info)
                else:
                    self.initiator_steps_label.config(text="none")

                if counter_value in self.reflector_map:
                    info = self._get_subevent_info(self.reflector_map[counter_value])
                    self.reflector_steps_label.config(text=info)
                else:
                    self.reflector_steps_label.config(text="none")
        except Exception as e:
            print(f"[ERROR] Exception in _update_display: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    def update_live_data(self, initiator: SubeventResults, reflector: SubeventResults):
        """Update live data from consumer thread - thread-safe"""
        def _update():
            self.live_initiator = initiator
            self.live_reflector = reflector

            # Add to historical data
            self.initiator_map[initiator.procedure_counter] = initiator
            self.reflector_map[reflector.procedure_counter] = reflector

            # Update spinbox range as new data arrives
            all_counters = sorted(set(self.initiator_map.keys()) | set(self.reflector_map.keys()))
            if all_counters:
                self.counter_spinbox.config(from_=min(all_counters), to=max(all_counters))

            if self.live_mode:
                # Update counter to match live data (prevent callback loop)
                self.counter_var.set(initiator.procedure_counter)
                self._update_display()

        # Schedule update on GUI thread
        self.root.after(0, _update)

    def _get_subevent_info(self, subevent):
        """Generate info string for a subevent"""
        steps = subevent.steps
        num_steps = len(steps)

        # Count unique channels
        channels = set(step.channel for step in steps)
        num_channels = len(channels)

        # Build simple info string
        info = f"{num_steps} steps, {num_channels} channels"

        return info

    def run(self):
        """Start the GUI event loop"""
        self.root.mainloop()


def launch_viewer(initiator_subevents: List = None, reflector_subevents: List = None):
    """Launch the CS Viewer GUI"""
    viewer = CSViewer(initiator_subevents, reflector_subevents)
    return viewer


def launch_viewer_blocking(initiator_subevents: List, reflector_subevents: List):
    """Launch the CS Viewer GUI in blocking mode (for file processing)"""
    viewer = CSViewer(initiator_subevents, reflector_subevents)
    viewer.run()
