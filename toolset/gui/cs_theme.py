from dataclasses import dataclass


@dataclass(frozen=True)
class _ThemeColors:
    # Backgrounds
    Background: str        # primary widget / text background
    AltBackground: str     # alternating row in hex view
    CanvasBackground: str  # steps tk.Canvas background
    # Text
    Foreground: str        # primary text
    SubtleForeground: str  # placeholder / disabled text
    MidForeground: str     # secondary text (missing-step labels)
    # Structure
    Border: str            # cell outlines
    # Selection
    Selection: str         # hex view selected-step highlight
    SelectionBorder: str   # canvas selection box border
    # Step cells - absent
    StepMissingBackground: str
    StepMissingForeground: str
    # Step mode-0 quality
    StepGoodBackground: str
    StepGoodForeground: str
    StepBadBackground: str
    StepBadForeground: str
    # Tone quality
    ToneHighBackground: str
    ToneHighForeground: str
    ToneMediumBackground: str
    ToneMediumForeground: str
    ToneLowBackground: str
    ToneLowForeground: str
    ToneExtensionBackground: str
    ToneExtensionForeground: str
    # Step mode 1 / 3 / unrecognised
    StepDefaultBackground: str
    StepDefaultForeground: str
    # Matplotlib
    PlotBackground: str
    PlotForeground: str
    PlotGridColor: str
    PlotPhaseBarColor: str
    PlotIniBarColor: str
    PlotRefBarColor: str


LIGHT_THEME = _ThemeColors(
    Background='#ffffff',
    AltBackground='#f0f0f0',
    CanvasBackground='#ffffff',
    Foreground='#333333',
    SubtleForeground='#888888',
    MidForeground='#666666',
    Border='#888888',
    Selection='#add8e6',
    SelectionBorder='#1565c0',
    StepMissingBackground='#cccccc',
    StepMissingForeground='#666666',
    StepGoodBackground='#4caf50',
    StepGoodForeground='#ffffff',
    StepBadBackground='#f44336',
    StepBadForeground='#ffffff',
    ToneHighBackground='#4caf50',
    ToneHighForeground='#ffffff',
    ToneMediumBackground='#ffeb3b',
    ToneMediumForeground='#333333',
    ToneLowBackground='#f44336',
    ToneLowForeground='#ffffff',
    ToneExtensionBackground='#9e9e9e',
    ToneExtensionForeground='#333333',
    StepDefaultBackground='#9e9e9e',
    StepDefaultForeground='#333333',
    PlotBackground='#ffffff',
    PlotForeground='#333333',
    PlotGridColor='#cccccc',
    PlotPhaseBarColor='#4472c4',
    PlotIniBarColor='#1565c0',
    PlotRefBarColor='#c62828',
)

DARK_THEME = _ThemeColors(
    Background='#1e1e1e',
    AltBackground='#252526',
    CanvasBackground='#1e1e1e',
    Foreground='#d4d4d4',
    SubtleForeground='#6e6e6e',
    MidForeground='#a0a0a0',
    Border='#454545',
    Selection='#264f78',
    SelectionBorder='#007acc',
    StepMissingBackground='#3c3c3c',
    StepMissingForeground='#6e6e6e',
    StepGoodBackground='#2d6a30',
    StepGoodForeground='#a5d6a7',
    StepBadBackground='#7d1f1f',
    StepBadForeground='#ffcdd2',
    ToneHighBackground='#2d6a30',
    ToneHighForeground='#a5d6a7',
    ToneMediumBackground='#7c5f00',
    ToneMediumForeground='#ffe082',
    ToneLowBackground='#7d1f1f',
    ToneLowForeground='#ffcdd2',
    ToneExtensionBackground='#383838',
    ToneExtensionForeground='#808080',
    StepDefaultBackground='#383838',
    StepDefaultForeground='#808080',
    PlotBackground='#1e1e1e',
    PlotForeground='#d4d4d4',
    PlotGridColor='#3a3a3a',
    PlotPhaseBarColor='#4fc3f7',
    PlotIniBarColor='#42a5f5',
    PlotRefBarColor='#ef5350',
)
