import tkinter as tk
from tkinter import ttk
from typing import List


class CSViewer:
    """GUI for viewing Channel Sounding data"""

    def __init__(self, initiator_subevents: List, reflector_subevents: List):
        self.initiator_subevents = initiator_subevents
        self.reflector_subevents = reflector_subevents

        # Create dictionaries for quick lookup by procedure_counter (filter out None values)
        self.initiator_map = {se.procedure_counter: se for se in initiator_subevents if se is not None}
        self.reflector_map = {se.procedure_counter: se for se in reflector_subevents if se is not None}

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

        # Procedure counter selection
        ttk.Label(main_frame, text="Procedure Counter:").grid(row=0, column=0, sticky=tk.W, pady=5)

        self.counter_var = tk.IntVar(value=procedure_counters[0] if procedure_counters else 0)
        counter_spinbox = ttk.Spinbox(
            main_frame,
            from_=min(procedure_counters) if procedure_counters else 0,
            to=max(procedure_counters) if procedure_counters else 0,
            textvariable=self.counter_var,
            width=15,
            command=self._on_counter_changed,
            values=procedure_counters
        )
        counter_spinbox.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        counter_spinbox.bind('<Return>', lambda e: self._on_counter_changed())

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=15)

        # Initiator steps display
        ttk.Label(main_frame, text="Initiator Steps:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.initiator_steps_label = ttk.Label(main_frame, text="")
        self.initiator_steps_label.grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Reflector steps display
        ttk.Label(main_frame, text="Reflector Steps:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.reflector_steps_label = ttk.Label(main_frame, text="")
        self.reflector_steps_label.grid(row=3, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=15)

        # Initial update
        self._on_counter_changed()

    def _on_counter_changed(self):
        """Handle procedure counter selection change"""
        counter = self.counter_var.get()

        # Get initiator info
        if counter in self.initiator_map:
            info = self._get_subevent_info(self.initiator_map[counter])
            self.initiator_steps_label.config(text=info)
        else:
            self.initiator_steps_label.config(text="none")

        # Get reflector info
        if counter in self.reflector_map:
            info = self._get_subevent_info(self.reflector_map[counter])
            self.reflector_steps_label.config(text=info)
        else:
            self.reflector_steps_label.config(text="none")

    def _get_subevent_info(self, subevent):
        """Generate info string for a subevent"""
        steps = subevent.steps
        num_steps = len(steps)

        # Count unique channels
        channels = set(step.channel for step in steps)
        num_channels = len(channels)

        # Build simple info string
        info = f"{num_steps} steps, {num_channels} channels: {sorted(channels)}"

        return info

    def run(self):
        """Start the GUI event loop"""
        self.root.mainloop()


def launch_viewer(initiator_subevents: List, reflector_subevents: List):
    """Launch the CS Viewer GUI"""
    viewer = CSViewer(initiator_subevents, reflector_subevents)
    viewer.run()
