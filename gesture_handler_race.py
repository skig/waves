"""Pygame gesture race game — dodge incoming cars with your arm.

Labels (case-insensitive):
  left   → player car moves left
  right  → player car moves right
  empty / center / anything else → no lateral movement

Usage:
    python3 run.py -i <ini> -r <ref> --uart --ml --gesture-handler gesture_handler_race.py
"""

import threading
import random
import pygame

# ── layout ───────────────────────────────────────────────────────────────────
_W, _H   = 480, 700        # window size
_RL      = 90              # road left edge
_RR      = 390             # road right edge
_RW      = _RR - _RL       # road width (300 px)
_LANES   = 3
_LW      = _RW // _LANES   # lane width (100 px)

# ── car geometry ─────────────────────────────────────────────────────────────
_PW, _PH = 54, 90          # player car size
_OW, _OH = 54, 82          # obstacle car size

# ── colours ───────────────────────────────────────────────────────────────────
_C_BG      = ( 20,  20,  20)
_C_ROAD    = ( 55,  55,  55)
_C_DASH    = (200, 200,  50)
_C_PLAYER  = ( 60, 180,  80)
_C_WIND_P  = (180, 255, 190)
_C_OBS     = (200,  60,  60)
_C_WIND_O  = (255, 190, 190)
_C_TEXT    = (220, 220, 220)
_C_OVERLAY = (  0,   0,   0, 150)

# ── speed / difficulty ────────────────────────────────────────────────────────
_FPS             = 60
_PLAYER_SPEED    = 5    # px / frame lateral
_OBS_SPEED_INIT  = 2    # px / frame scroll at start
_OBS_SPEED_MAX   = 8
_SPAWN_MAX       = 150  # frames between spawns at start
_SPAWN_MIN       = 60   # minimum spawn interval
# Minimum number of consecutive identical gesture readings before it is accepted.
# Raise to filter out more flicker, lower for faster response.
_DEBOUNCE_COUNT  = 3

# ── module-level state ────────────────────────────────────────────────────────
_thread         = None
_running        = False
_direction      = 'none'   # 'left' | 'right' | 'none'
_pending_label  = 'none'   # candidate label not yet confirmed
_pending_count  = 0        # how many times in a row we've seen _pending_label
_lock           = threading.Lock()


# ── public handler interface ──────────────────────────────────────────────────

def on_recognition_start(classes: list) -> None:
    global _thread, _running, _direction, _pending_label, _pending_count
    with _lock:
        _direction     = 'none'
        _pending_label = 'none'
        _pending_count = 0
    _running = True
    _thread = threading.Thread(target=_game_loop, daemon=True, name='race-game')
    _thread.start()


def on_gesture(label: str, confidence: float, probabilities: dict) -> None:
    global _direction, _pending_label, _pending_count
    lbl = label.lower().strip()
    print(f"Gesture: {lbl} (confidence: {confidence:.2f})")
    d = 'left' if lbl == 'left' else 'right' if lbl == 'right' else 'none'
    with _lock:
        if d == 'none':
            # stop immediately — no debounce needed
            _pending_label = 'none'
            _pending_count = 0
            _direction     = 'none'
        else:
            if d == _pending_label:
                _pending_count += 1
            else:
                _pending_label = d
                _pending_count = 1
            if _pending_count >= _DEBOUNCE_COUNT:
                _direction = _pending_label


def on_recognition_stop() -> None:
    global _running, _thread
    _running = False
    if _thread is not None:
        _thread.join(timeout=2.0)
        _thread = None


# ── game internals ────────────────────────────────────────────────────────────

def _new_state() -> dict:
    px = _RL + (_RW - _PW) // 2
    py = _H - _PH - 50
    return {
        'player': pygame.Rect(px, py, _PW, _PH),
        'obs':    [],    # list of pygame.Rect
        'lane_queue': [],  # shuffled lane queue — ensures equal per-lane spawn distribution
        'score':  0,
        'frame':  0,
        'mark_y': 0,     # road-marking scroll offset
        'dead':   False,
    }


def _blit_center(screen, surf, cy, cx=None) -> None:
    if cx is None:
        cx = _W // 2
    screen.blit(surf, surf.get_rect(center=(cx, cy)))


def _game_loop() -> None:
    global _running

    pygame.init()
    screen = pygame.display.set_mode((_W, _H))
    pygame.display.set_caption('Gesture Race')
    clock      = pygame.time.Clock()
    font_big   = pygame.font.SysFont(None, 56)
    font_med   = pygame.font.SysFont(None, 34)
    font_small = pygame.font.SysFont(None, 22)

    state = _new_state()

    while _running:
        clock.tick(_FPS)

        # ── events ───────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                _running = False
                break
            if event.type == pygame.KEYDOWN and state['dead']:
                if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                    state = _new_state()

        if not _running:
            break

        f = state['frame']

        # ── update ───────────────────────────────────────────────────────────
        if not state['dead']:
            # difficulty scales with time
            obs_speed    = min(_OBS_SPEED_MAX, _OBS_SPEED_INIT + f // (_FPS * 15))
            spawn_frames = max(_SPAWN_MIN, _SPAWN_MAX - f // (_FPS * 8))

            # lateral player movement from gesture
            with _lock:
                d = _direction
            p = state['player']
            if d == 'left':
                p.x = max(_RL, p.x - _PLAYER_SPEED)
            elif d == 'right':
                p.x = min(_RR - _PW, p.x + _PLAYER_SPEED)

            # spawn obstacle in a random lane  (disabled for testing)
            if f % spawn_frames == 0:
                if not state['lane_queue']:
                    state['lane_queue'] = list(range(_LANES))
                    random.shuffle(state['lane_queue'])
                lane = state['lane_queue'].pop()
                ox = _RL + lane * _LW + (_LW - _OW) // 2
                state['obs'].append(pygame.Rect(ox, -_OH, _OW, _OH))

            # move obstacles; count avoided ones as score  (disabled for testing)
            remaining = []
            for o in state['obs']:
                o.y += obs_speed
                if o.y >= _H:
                    state['score'] += 1
                else:
                    remaining.append(o)
            state['obs'] = remaining

            # collision detection  (disabled for testing)
            for o in state['obs']:
                if p.colliderect(o):
                    state['dead'] = True
                    break

            # scroll road markings
            state['mark_y'] = (state['mark_y'] + obs_speed) % 60
            state['frame'] += 1

        # ── render ───────────────────────────────────────────────────────────
        screen.fill(_C_BG)

        # road surface
        pygame.draw.rect(screen, _C_ROAD, (_RL, 0, _RW, _H))

        # dashed lane dividers
        for lane in range(1, _LANES):
            lx = _RL + lane * _LW
            y  = -60 + state['mark_y']
            while y < _H:
                pygame.draw.rect(screen, _C_DASH, (lx - 2, y, 4, 35))
                y += 60

        # obstacle cars  (disabled for testing)
        for o in state['obs']:
            pygame.draw.rect(screen, _C_OBS, o)
            # windshield
            pygame.draw.rect(screen, _C_WIND_O,
                             pygame.Rect(o.x + 8, o.y + 10, _OW - 16, _OH // 3))

        # player car
        p = state['player']
        pygame.draw.rect(screen, _C_PLAYER, p)
        # windshield (rear-facing, so near bottom of car body)
        pygame.draw.rect(screen, _C_WIND_P,
                         pygame.Rect(p.x + 8, p.y + _PH // 2, _PW - 16, _PH // 3))

        # HUD
        screen.blit(font_med.render(f"Score: {state['score']}", True, _C_TEXT), (10, 10))
        with _lock:
            lbl_txt = _direction
        screen.blit(font_small.render(f'Gesture: {lbl_txt}', True, _C_TEXT), (10, 50))

        # game-over overlay
        if state['dead']:
            overlay = pygame.Surface((_W, _H), pygame.SRCALPHA)
            overlay.fill(_C_OVERLAY)
            screen.blit(overlay, (0, 0))

            _blit_center(screen,
                         font_big.render('GAME OVER', True, (255, 80, 80)),
                         _H // 2 - 55)
            _blit_center(screen,
                         font_med.render(f"Score: {state['score']}", True, _C_TEXT),
                         _H // 2 + 10)
            _blit_center(screen,
                         font_small.render('Press R / Enter / Space to restart', True, _C_TEXT),
                         _H // 2 + 55)

        pygame.display.flip()

    pygame.quit()
