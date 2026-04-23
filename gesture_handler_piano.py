"""Gesture handler — piano octave visualizer with note playback.

Expects gesture labels to be note names (C, C#, D, D#, E, F, F#, G, G#, A, A#, B)
and "empty" for silence.  Enharmonic flat names (Db, Eb, Gb, Ab, Bb) are also accepted.

Plays a synthesized piano tone when a note has the highest probability and shows which
key is pressed on a rendered piano octave.  No sound is played for the "empty" label.

Dependencies (beyond the project requirements):
    sudo apt install python3-pygame

Usage:
    python3 run.py -i <ini> -r <ref> --uart --ml --gesture-handler gesture_handler_piano.py
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

try:
    import pygame
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=512)
    pygame.mixer.init()
    _AUDIO_AVAILABLE = True
except Exception as _e:
    _AUDIO_AVAILABLE = False
    print(f'[piano handler] pygame not available — audio disabled ({_e}). Install with: sudo apt install python3-pygame')

# ---------------------------------------------------------------------------
# Note definitions
# ---------------------------------------------------------------------------

# Canonical note order (sharps)
_NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Enharmonic aliases → canonical
_ENHARMONIC = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}

# Frequencies for octave 4
_FREQ = {
    'C':  261.63, 'C#': 277.18,
    'D':  293.66, 'D#': 311.13,
    'E':  329.63,
    'F':  349.23, 'F#': 369.99,
    'G':  392.00, 'G#': 415.30,
    'A':  440.00, 'A#': 466.16,
    'B':  493.88,
}

_WHITE_NOTES = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
_BLACK_NOTES = ['C#', 'D#', 'F#', 'G#', 'A#']

# x-centre of each black key expressed as offset from the left edge of the octave
# (white key width = 1.0 unit, octave spans [0, 7])
_BLACK_X = {'C#': 0.72, 'D#': 1.72, 'F#': 3.72, 'G#': 4.72, 'A#': 5.72}

_SAMPLE_RATE = 44100
_NOTE_DURATION = 0.6   # seconds


def _canonicalize(label: str) -> str:
    """Normalize a note label to the canonical sharp form, or return as-is."""
    return _ENHARMONIC.get(label, label)


def _synthesize(freq: float, duration: float = _NOTE_DURATION, sr: int = _SAMPLE_RATE) -> np.ndarray:
    """Generate a piano-like tone via additive synthesis with an exponential decay envelope."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # Harmonic amplitudes (approximate piano timbre)
    harmonics = [
        (1, 1.00),
        (2, 0.50),
        (3, 0.25),
        (4, 0.12),
        (5, 0.06),
        (6, 0.03),
    ]
    wave = sum(amp * np.sin(2 * np.pi * freq * n * t) for n, amp in harmonics)

    # Exponential decay envelope — fast attack, natural decay
    attack_samples = int(sr * 0.005)
    envelope = np.exp(-4.0 * t / duration)
    envelope[:attack_samples] = np.linspace(0, 1, attack_samples)

    wave *= envelope
    wave /= np.abs(wave).max() + 1e-9  # normalize to [-1, 1]
    wave = (wave * 0.7 * 32767).astype(np.int16)  # pygame expects 16-bit int
    return wave


# Cache synthesized sounds to avoid re-computing every call
_sound_cache: dict = {}


def _get_sound(freq: float) -> 'pygame.mixer.Sound':
    if freq not in _sound_cache:
        wave = _synthesize(freq)
        sound = pygame.sndarray.make_sound(wave)
        _sound_cache[freq] = sound
    return _sound_cache[freq]


def _play_note(freq: float) -> None:
    """Play a synthesized note without blocking the GUI."""
    if not _AUDIO_AVAILABLE:
        return
    pygame.mixer.stop()
    _get_sound(freq).play()


# ---------------------------------------------------------------------------
# Piano drawing helpers
# ---------------------------------------------------------------------------

_WHITE_W = 1.0
_WHITE_H = 1.0
_BLACK_W = 0.55
_BLACK_H = 0.60

_COLOR_WHITE_IDLE    = '#f5f5f5'
_COLOR_WHITE_ACTIVE  = '#a5d6a7'   # green highlight
_COLOR_BLACK_IDLE    = '#212121'
_COLOR_BLACK_ACTIVE  = '#2e7d32'   # dark green highlight
_COLOR_EMPTY_TINT    = '#ef9a9a'   # red tint when "empty" is active


def _draw_piano(ax: plt.Axes, active_note: str | None, is_empty: bool) -> None:
    """Redraw the octave on *ax*. active_note is the canonical note name or None."""
    ax.cla()
    ax.set_xlim(-0.1, 7.1)
    ax.set_ylim(-0.05, 1.1)
    ax.set_aspect('equal')
    ax.axis('off')

    bg = _COLOR_EMPTY_TINT if is_empty else '#1e1e1e'
    ax.set_facecolor(bg)

    # --- white keys ---
    for i, note in enumerate(_WHITE_NOTES):
        color = _COLOR_WHITE_ACTIVE if note == active_note else _COLOR_WHITE_IDLE
        rect = mpatches.FancyBboxPatch(
            (i * _WHITE_W + 0.02, 0.02),
            _WHITE_W - 0.04, _WHITE_H - 0.04,
            boxstyle='round,pad=0.01',
            facecolor=color, edgecolor='#424242', linewidth=1.5,
        )
        ax.add_patch(rect)
        ax.text(
            i * _WHITE_W + _WHITE_W / 2, 0.10, note,
            ha='center', va='bottom', fontsize=9,
            color='#212121' if color == _COLOR_WHITE_IDLE else '#1b5e20',
            fontweight='bold' if note == active_note else 'normal',
        )

    # --- black keys (drawn on top) ---
    for note, cx in _BLACK_X.items():
        color = _COLOR_BLACK_ACTIVE if note == active_note else _COLOR_BLACK_IDLE
        rect = mpatches.FancyBboxPatch(
            (cx - _BLACK_W / 2, _WHITE_H - _BLACK_H),
            _BLACK_W, _BLACK_H,
            boxstyle='round,pad=0.01',
            facecolor=color, edgecolor='#616161', linewidth=1.0, zorder=3,
        )
        ax.add_patch(rect)
        ax.text(
            cx, _WHITE_H - _BLACK_H + 0.05, note,
            ha='center', va='bottom', fontsize=6.5,
            color='#a5d6a7' if note == active_note else '#9e9e9e',
            fontweight='bold' if note == active_note else 'normal',
            zorder=4,
        )


# ---------------------------------------------------------------------------
# Handler state
# ---------------------------------------------------------------------------

_fig = None
_ax = None
_classes = None
_last_active: str | None = None  # last note that was actually played


def on_recognition_start(classes: list) -> None:
    global _fig, _ax, _classes, _last_active

    _classes = classes
    _last_active = None

    _fig, _ax = plt.subplots(figsize=(8, 3))
    _fig.patch.set_facecolor('#1e1e1e')
    _fig.canvas.manager.set_window_title('Piano — gesture recognition')

    _draw_piano(_ax, active_note=None, is_empty=False)
    _fig.tight_layout()
    plt.ion()
    plt.show()


def on_gesture(label: str, confidence: float, probabilities: dict) -> None:
    global _last_active

    if _fig is None or _ax is None:
        return

    canonical = _canonicalize(label)
    is_empty = (canonical == 'empty' or label == 'empty')

    # Determine note to highlight
    active_note = None if is_empty else (canonical if canonical in _FREQ else None)

    # Play sound only when the active note changes (avoid re-triggering on every frame)
    if active_note != _last_active:
        if active_note is not None:
            _play_note(_FREQ[active_note])
        _last_active = active_note

    _draw_piano(_ax, active_note=active_note, is_empty=is_empty)

    title = 'empty' if is_empty else f'{label}  ({confidence:.0%})'
    _ax.set_title(title, color='#eeeeee', pad=6, fontsize=12)

    _fig.canvas.draw_idle()
    _fig.canvas.flush_events()


def on_recognition_stop() -> None:
    global _fig, _ax, _classes, _last_active

    if _AUDIO_AVAILABLE:
        pygame.mixer.stop()

    if _fig is not None:
        plt.close(_fig)

    _fig = _ax = _classes = _last_active = None
