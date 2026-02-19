import os, json, pygame, math, uuid
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum


class Phase(Enum):
    WORK        = ('Pomodoro',    'work')
    SHORT_BREAK = ('Short Break', 'short_break')
    LONG_BREAK  = ('Long Break',  'long_break')

    def __init__(self, title, key):
        self.title = title
        self.key   = key


class C:
    BG       = (30,  30,  40)
    SURFACE  = (42,  42,  56)
    SURFACE2 = (54,  54,  72)
    BORDER   = (70,  70,  92)
    WHITE    = (242, 242, 250)
    DIM      = (148, 148, 172)
    YELLOW   = (255, 210, 60)
    RED      = (232, 78,  78)
    RED_H    = (245, 100, 100)
    GREEN    = (78,  200, 120)
    GREEN_H  = (100, 220, 140)
    TEAL     = (78,  180, 200)
    TEAL_H   = (100, 200, 220)


ACCENT     = {Phase.WORK: C.RED,   Phase.SHORT_BREAK: C.GREEN,   Phase.LONG_BREAK: C.TEAL}
ACCENT_HOV = {Phase.WORK: C.RED_H, Phase.SHORT_BREAK: C.GREEN_H, Phase.LONG_BREAK: C.TEAL_H}


class Config:
    DEFAULTS = {
        'work_time': 25, 'break_time': 5, 'long_break': 15,
        'sessions_until_long': 4, 'auto_continue': False,
        'sound_enabled': True, 'music_enabled': True, 'daily_goal': 8
    }

    def __init__(self):
        self.path = os.path.expanduser('~/.pomodoro_config')
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError):
                pass
        return self.DEFAULTS.copy()

    def save(self):
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def __getitem__(self, key):
        return self.data.get(key, self.DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def get(self, key, default=None):
        return self.data.get(key, self.DEFAULTS.get(key, default))


class DataStore:
    def __init__(self, path):
        self.path = os.path.expanduser(path)

    def write(self, data):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'a') as f:
            f.write(json.dumps(data) + '\n')

    def read_all(self):
        if not os.path.exists(self.path):
            return []
        rows = []
        with open(self.path) as f:
            for line in f:
                try:
                    e = json.loads(line.strip())
                    e['start'] = datetime.strptime(e['start'], '%Y-%m-%d %H:%M:%S.%f')
                    rows.append(e)
                except (json.JSONDecodeError, ValueError):
                    continue
        return rows


class Presets:
    def __init__(self):
        self.path = os.path.expanduser('~/.pomodoro_presets')
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError):
                pass
        return {}

    def save(self):
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def add(self, name, work, brk, long_brk, sessions):
        self.data[name] = {
            'work_time': work, 'break_time': brk,
            'long_break': long_brk, 'sessions': sessions
        }
        self.save()

    def get(self, name):
        return self.data.get(name)

    def list_all(self):
        return self.data


class Tasks:
    def __init__(self):
        self.path  = os.path.expanduser('~/.pomodoro_tasks')
        self.tasks = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError):
                pass
        return {}

    def save(self):
        with open(self.path, 'w') as f:
            json.dump(self.tasks, f, indent=2)

    def add(self, tid, title):
        self.tasks[tid] = {'title': title, 'completed': False, 'created': str(datetime.now())}
        self.save()

    def toggle(self, tid):
        if tid in self.tasks:
            self.tasks[tid]['completed'] = not self.tasks[tid].get('completed', False)
            self.save()

    def list_all(self):
        return self.tasks


class Audio:
    _ready         = False
    _music_file    = None
    _music_enabled = True
    _sfx_enabled   = True

    @classmethod
    def _init(cls):
        if not cls._ready:
            try:
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()
                pygame.mixer.set_num_channels(8)
                cls._ready = True
            except Exception:
                pass

    @classmethod
    def configure(cls, music_enabled, sfx_enabled):
        cls._music_enabled = music_enabled
        cls._sfx_enabled   = sfx_enabled

    @classmethod
    def set_music(cls, enabled):
        cls._music_enabled = enabled
        if not enabled:
            cls._stop_music()

    @classmethod
    def set_sfx(cls, enabled):
        cls._sfx_enabled = enabled

    @classmethod
    def play_sfx(cls, name):
        if not cls._sfx_enabled:
            return
        cls._init()
        base = os.path.dirname(os.path.abspath(__file__))
        files = {
            'start':    'TIME_STARTED.mp3',
            'complete': 'SESSION_COMPLETED.mp3',
            'notify':   'NOTIFICATION.mp3',
        }
        fname = files.get(name)
        if not fname:
            return
        path = os.path.join(base, fname)
        if not os.path.exists(path):
            return
        try:
            snd = pygame.mixer.Sound(path)
            ch  = pygame.mixer.find_channel(True)
            if ch:
                ch.play(snd)
        except Exception:
            pass

    @classmethod
    def start_music(cls):
        if not cls._music_enabled:
            return
        cls._init()
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, 'WORKING_MUSIC.mp3')
        if not os.path.exists(path):
            return
        try:
            if cls._music_file != path:
                pygame.mixer.music.load(path)
                cls._music_file = path
                pygame.mixer.music.play(-1)
            elif not pygame.mixer.music.get_busy():
                pygame.mixer.music.play(-1)
            else:
                pygame.mixer.music.unpause()
        except Exception:
            pass

    @classmethod
    def pause_music(cls):
        try:
            pygame.mixer.music.pause()
        except Exception:
            pass

    @classmethod
    def _stop_music(cls):
        try:
            pygame.mixer.music.stop()
            cls._music_file = None
        except Exception:
            pass

    @classmethod
    def stop_music(cls):
        cls._stop_music()


class Stats:
    def __init__(self, store):
        self.store = store

    def get_today(self):
        today = datetime.now().date()
        work  = [s for s in self.store.read_all()
                 if s['type'] == 'work' and s['start'].date() == today]
        return sum(s['duration'] for s in work) / 3600, len(work)

    def get_week(self):
        ws   = datetime.now().date() - timedelta(days=datetime.now().weekday())
        work = [s for s in self.store.read_all()
                if s['type'] == 'work' and s['start'].date() >= ws]
        wd   = defaultdict(lambda: {'hours': 0, 'sessions': 0})
        for s in work:
            d = s['start'].date()
            wd[d]['hours']    += s['duration'] / 3600
            wd[d]['sessions'] += 1
        return wd

    def get_total(self):
        work = [s for s in self.store.read_all() if s['type'] == 'work']
        return sum(s['duration'] for s in work) / 3600, len(work)


def rekt(surface, color, rect, radius=0, border=None, bw=1):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surface, border, rect, bw, border_radius=radius)


def txt(surface, string, font, color, cx, y, anchor='center'):
    surf = font.render(string, True, color)
    if anchor == 'center':
        surface.blit(surf, (cx - surf.get_width() // 2, y))
    elif anchor == 'left':
        surface.blit(surf, (cx, y))
    elif anchor == 'right':
        surface.blit(surf, (cx - surf.get_width(), y))
    return surf.get_size()


def ring(surface, cx, cy, radius, progress, color, thickness=11):
    for i in range(360):
        a  = math.radians(i - 90)
        na = math.radians(i + 1 - 90)
        x1 = cx + radius * math.cos(a)
        y1 = cy + radius * math.sin(a)
        x2 = cx + radius * math.cos(na)
        y2 = cy + radius * math.sin(na)
        pygame.draw.line(surface, C.SURFACE2, (int(x1), int(y1)), (int(x2), int(y2)), thickness)
    filled = int(360 * progress)
    for i in range(filled):
        a  = math.radians(i - 90)
        na = math.radians(i + 1 - 90)
        x1 = cx + radius * math.cos(a)
        y1 = cy + radius * math.sin(a)
        x2 = cx + radius * math.cos(na)
        y2 = cy + radius * math.sin(na)
        pygame.draw.line(surface, color, (int(x1), int(y1)), (int(x2), int(y2)), thickness)


def tomato(surface, cx, cy, size, accent):
    pygame.draw.circle(surface, C.SURFACE2, (cx, cy), size + 3)
    pygame.draw.circle(surface, accent,     (cx, cy), size)
    sw = max(4, size // 10)
    sh = size // 3
    pygame.draw.rect(surface, C.GREEN, (cx - sw // 2, cy - size - sh // 2, sw, sh + 4))
    for side in (-1, 1):
        pts = [
            (cx,                    cy - size + 6),
            (cx + side * size // 3, cy - size - size // 5),
            (cx + side * size // 6, cy - size + 4),
        ]
        pygame.draw.polygon(surface, C.GREEN, pts)


def dots(surface, cx, y, completed, total):
    r, gap = 5, 16
    sx = cx - (total - 1) * gap // 2
    for i in range(total):
        col = C.WHITE if i < completed else C.SURFACE2
        pygame.draw.circle(surface, col, (sx + i * gap, y), r)


def checkbox(surface, cx, cy, done):
    col = C.GREEN if done else C.BORDER
    pygame.draw.circle(surface, col, (cx, cy), 8)
    if done:
        pygame.draw.line(surface, C.WHITE, (cx - 4, cy),     (cx - 1, cy + 3), 2)
        pygame.draw.line(surface, C.WHITE, (cx - 1, cy + 3), (cx + 4, cy - 3), 2)


class PomodoroTimer:
    def __init__(self, config, store, screen):
        self.config = config
        self.store  = store
        self.screen = screen
        self.count  = 0
        self.active = True
        self.btns   = {}

    def run_phase(self, duration, phase, work_count, total, task, auto_continue):
        remaining  = duration * 60
        running    = True
        paused     = False
        skipped    = False
        auto_t     = None
        start      = datetime.now()
        ac         = ACCENT[phase]
        music_live = self.config.get('music_enabled', True)

        if phase == Phase.WORK:
            Audio.start_music()

        fhuge  = pygame.font.Font(None, 116)
        ftitle = pygame.font.Font(None, 50)
        fsub   = pygame.font.Font(None, 27)
        fsmall = pygame.font.Font(None, 23)
        ftiny  = pygame.font.Font(None, 20)

        while remaining > 0 and running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    Audio.stop_music()
                    pygame.quit()
                    return 0, False, True

                if e.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(e.size, pygame.RESIZABLE)

                if e.type == pygame.MOUSEBUTTONDOWN:
                    for action, rect in self.btns.items():
                        if rect.collidepoint(e.pos):
                            if action == 'pause':
                                paused = not paused
                                auto_t = None
                                if paused:
                                    Audio.pause_music()
                                elif phase == Phase.WORK:
                                    Audio.start_music()
                            elif action == 'skip':
                                skipped = True
                                running = False
                            elif action == 'music':
                                music_live = not music_live
                                self.config['music_enabled'] = music_live
                                Audio.set_music(music_live)
                                if music_live and phase == Phase.WORK and not paused:
                                    Audio.start_music()
                            elif action == 'stop':
                                Audio.stop_music()
                                return 0, False, True

                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_SPACE:
                        paused = not paused
                        auto_t = None
                        if paused:
                            Audio.pause_music()
                        elif phase == Phase.WORK:
                            Audio.start_music()
                    elif e.key == pygame.K_s:
                        skipped = True
                        running = False
                    elif e.key == pygame.K_m:
                        music_live = not music_live
                        self.config['music_enabled'] = music_live
                        Audio.set_music(music_live)
                        if music_live and phase == Phase.WORK and not paused:
                            Audio.start_music()
                    elif e.key == pygame.K_ESCAPE:
                        Audio.stop_music()
                        return 0, False, True

            if not paused:
                remaining = max(0, duration * 60 - int((datetime.now() - start).total_seconds()))
                if remaining == 0:
                    running = False

            self._draw(phase, ac, remaining, duration, work_count, total,
                       task, paused, music_live, fhuge, ftitle, fsub, fsmall, ftiny)
            pygame.display.flip()
            pygame.time.Clock().tick(60)

            if remaining == 0 and not paused and auto_t is None and auto_continue:
                auto_t = datetime.now()
            if auto_t and (datetime.now() - auto_t).total_seconds() >= 3:
                break

        if phase == Phase.WORK:
            Audio.stop_music()

        return remaining, skipped, False

    def _draw(self, phase, ac, remaining, duration, work_count, total,
              task, paused, music_live, fhuge, ftitle, fsub, fsmall, ftiny):
        W, H = self.screen.get_size()
        cx   = W // 2
        self.screen.fill(C.BG)

        pygame.draw.rect(self.screen, ac, pygame.Rect(0, 0, W, 4))

        txt(self.screen, phase.title, ftitle, C.WHITE, cx, 26)

        sub = f"Session {work_count} of {total}" if phase == Phase.WORK else "Take a break"
        txt(self.screen, sub, fsub, C.DIM, cx, 78)

        completed = (work_count - 1) if phase == Phase.WORK else work_count
        dots(self.screen, cx, 118, completed, total)

        ts  = max(52, min(W, H) // 9)
        rr  = ts + 26
        ty  = max(196, int(H * 0.35))

        progress = 1 - (remaining / (duration * 60)) if duration > 0 else 0
        ring(self.screen, cx, ty, rr, progress, ac)
        tomato(self.screen, cx, ty, ts, ac)

        mins, secs = divmod(int(remaining), 60)
        tsf = fhuge.render(f"{mins:02d}:{secs:02d}", True, C.WHITE)
        timer_y = ty + rr + 34
        self.screen.blit(tsf, (cx - tsf.get_width() // 2, timer_y))

        info_y = timer_y + tsf.get_height() + 10
        if paused:
            txt(self.screen, "paused", fsmall, C.YELLOW, cx, info_y)
            info_y += 22
        if task and phase == Phase.WORK:
            txt(self.screen, task, fsmall, C.DIM, cx, info_y)

        btn_h  = 44
        btn_y  = H - 80
        gap    = 10
        widths = [136, 86, 136, 86]
        labels = ["Resume" if paused else "Pause", "Skip",
                  "Music: On" if music_live else "Music: Off", "Stop"]
        colors = [ac, C.SURFACE2, ac if music_live else C.SURFACE2, C.SURFACE2]
        actions = ['pause', 'skip', 'music', 'stop']

        total_w = sum(widths) + gap * (len(widths) - 1)
        bx      = cx - total_w // 2
        self.btns = {}

        for i, (lbl, bw, col, action) in enumerate(zip(labels, widths, colors, actions)):
            rect    = pygame.Rect(bx, btn_y, bw, btn_h)
            mouse   = pygame.mouse.get_pos()
            hovered = rect.collidepoint(mouse)
            bg      = tuple(min(255, v + 16) for v in col) if hovered else col
            rekt(self.screen, bg, rect, radius=11)
            txt(self.screen, lbl, fsmall, C.WHITE, bx + bw // 2, btn_y + btn_h // 2 - 9)
            self.btns[action] = rect
            bx += bw + gap

        hints = "SPACE  pause    S  skip    M  music    ESC  stop"
        txt(self.screen, hints, ftiny, C.BORDER, cx, btn_y - 22)

    def start_session(self, work_time, break_time, long_break,
                      sessions_per_cycle, task, tags, auto_continue):
        Audio.configure(
            music_enabled=self.config.get('music_enabled', True),
            sfx_enabled=self.config.get('sound_enabled', True),
        )
        Audio.play_sfx('start')

        while self.active:
            self.count += 1

            if self.count >= sessions_per_cycle:
                remaining, skipped, exit_flag = self.run_phase(
                    long_break, Phase.LONG_BREAK,
                    self.count, sessions_per_cycle, task, auto_continue)
                if exit_flag:
                    break
                if not skipped:
                    self.store.write({
                        'start': str(datetime.now()),
                        'end':   str(datetime.now() + timedelta(seconds=long_break * 60)),
                        'duration': long_break * 60,
                        'type': 'break', 'task': task, 'tags': tags or []
                    })
                else:
                    Audio.play_sfx('notify')
                self.count = 0
                continue

            for phase, dur in [(Phase.WORK, work_time), (Phase.SHORT_BREAK, break_time)]:
                start = datetime.now()

                remaining, skipped, exit_flag = self.run_phase(
                    dur, phase, self.count, sessions_per_cycle, task, auto_continue)

                if exit_flag:
                    self.active = False
                    break

                if not skipped:
                    self.store.write({
                        'start':    str(start),
                        'end':      str(start + timedelta(seconds=dur * 60)),
                        'duration': dur * 60,
                        'type':     'work' if phase == Phase.WORK else 'break',
                        'task': task, 'tags': tags or []
                    })

                if phase == Phase.WORK:
                    Audio.play_sfx('complete')
                elif skipped:
                    Audio.play_sfx('notify')

        Audio.stop_music()
        Audio.play_sfx('start')
        pygame.quit()


def setup():
    pygame.init()
    s = pygame.display.set_mode((480, 760), pygame.RESIZABLE)
    pygame.display.set_caption("Pomodoro")
    return s


class Menu:
    def __init__(self, config, store, presets):
        self.config  = config
        self.store   = store
        self.presets = presets
        self.stats   = Stats(store)
        self.tasks   = Tasks()
        self.screen  = setup()
        self.clock   = pygame.time.Clock()
        self.running = True
        self.view    = 'main'
        self.btns    = {}
        self.tbns    = {}
        self.pbns    = {}

        self.fhuge  = pygame.font.Font(None, 96)
        self.ftitle = pygame.font.Font(None, 52)
        self.fmed   = pygame.font.Font(None, 34)
        self.fbody  = pygame.font.Font(None, 27)
        self.fsmall = pygame.font.Font(None, 23)
        self.ftiny  = pygame.font.Font(None, 20)

    def _btn(self, rect, label, ac=None, small=False):
        mouse   = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse)
        if ac:
            bg = tuple(min(255, v + 18) for v in ac) if hovered else ac
        else:
            bg = C.SURFACE2 if hovered else C.SURFACE
        rekt(self.screen, bg, rect, radius=12,
             border=C.BORDER if not ac else None, bw=1)
        f = self.fsmall if small else self.fbody
        txt(self.screen, label, f, C.WHITE,
            rect.x + rect.w // 2, rect.y + rect.h // 2 - 9)

    def draw_main(self):
        W, H = self.screen.get_size()
        cx   = W // 2
        self.screen.fill(C.BG)
        self.btns = {}
        self.tbns = {}

        pygame.draw.rect(self.screen, C.RED, pygame.Rect(0, 0, W, 4))

        txt(self.screen, "Pomodoro", self.ftitle, C.WHITE, cx, 26)

        tw  = 132
        tgp = 8
        tx  = cx - (3 * tw + 2 * tgp) // 2
        for lbl, key in [("Pomodoro", 'work_time'), ("Short Break", 'break_time'), ("Long Break", 'long_break')]:
            r = pygame.Rect(tx, 80, tw, 40)
            rekt(self.screen, C.SURFACE, r, radius=10, border=C.BORDER, bw=1)
            txt(self.screen, lbl,                    self.ftiny,  C.DIM,   r.x + r.w // 2, r.y + 5)
            txt(self.screen, f"{self.config[key]}m", self.fsmall, C.WHITE, r.x + r.w // 2, r.y + 20)
            tx += tw + tgp

        pygame.draw.line(self.screen, C.BORDER, (24, 134), (W - 24, 134), 1)

        txt(self.screen, f"{self.config['work_time']:02d}:00", self.fhuge, C.WHITE, cx, 152)

        dots(self.screen, cx, 268, 0, self.config['sessions_until_long'])

        sr = pygame.Rect(cx - 110, 294, 220, 54)
        self.btns['start'] = sr
        self._btn(sr, "START", ac=C.RED)

        nav = [("Stats", 'stats'), ("Tasks", 'tasks'), ("Presets", 'presets'), ("Settings", 'settings')]
        nw  = (W - 48 - 3 * 8) // 4
        nx  = 24
        for lbl, key in nav:
            r = pygame.Rect(nx, 368, nw, 40)
            self.btns[key] = r
            self._btn(r, lbl, small=True)
            nx += nw + 8

        pygame.draw.line(self.screen, C.BORDER, (24, 424), (W - 24, 424), 1)
        txt(self.screen, "Tasks", self.fbody, C.DIM, 24, 434, anchor='left')

        all_tasks = self.tasks.list_all()
        ty = 464
        if all_tasks:
            for tid, td in list(all_tasks.items())[:4]:
                done = td.get('completed', False)
                r    = pygame.Rect(24, ty, W - 48, 40)
                self.tbns[tid] = r
                rekt(self.screen, C.SURFACE, r, radius=8, border=C.BORDER, bw=1)
                checkbox(self.screen, r.x + 20, r.y + 20, done)
                tc = C.DIM if done else C.WHITE
                txt(self.screen, td['title'], self.fsmall, tc, r.x + 38, r.y + 11, anchor='left')
                ty += 50
        else:
            txt(self.screen, "No tasks yet", self.fsmall, C.DIM, cx, ty + 8)
            ty += 36

        addr = pygame.Rect(24, ty + 6, W - 48, 36)
        self.btns['add_task'] = addr
        self._btn(addr, "+ Add Task", small=True)

        hours_today, sessions_today = self.stats.get_today()
        daily_goal = self.config.get('daily_goal', 8)
        progress   = min(1.0, hours_today / daily_goal) if daily_goal else 0

        prog_y = H - 66
        pygame.draw.line(self.screen, C.BORDER, (24, prog_y - 12), (W - 24, prog_y - 12), 1)
        txt(self.screen, "Today", self.ftiny, C.DIM, 24, prog_y - 8, anchor='left')
        txt(self.screen, f"{hours_today:.1f}h  /  {sessions_today} sessions",
            self.fsmall, C.WHITE, W - 24, prog_y - 8, anchor='right')
        bar = pygame.Rect(24, prog_y + 10, W - 48, 8)
        rekt(self.screen, C.SURFACE2, bar, radius=4)
        fw = int((W - 48) * progress)
        if fw > 0:
            rekt(self.screen, C.RED, pygame.Rect(24, prog_y + 10, fw, 8), radius=4)

    def draw_stats(self):
        W, H = self.screen.get_size()
        cx   = W // 2
        self.screen.fill(C.BG)
        self.btns = {}
        pygame.draw.rect(self.screen, C.RED, pygame.Rect(0, 0, W, 4))
        txt(self.screen, "Statistics", self.ftitle, C.WHITE, cx, 26)
        pygame.draw.line(self.screen, C.BORDER, (24, 78), (W - 24, 78), 1)

        ht, st = self.stats.get_today()
        ha, sa = self.stats.get_total()
        cw = (W - 56) // 2
        for i, (lbl, val, sub) in enumerate([
            ("TODAY",    f"{ht:.1f}h", f"{st} sessions"),
            ("ALL TIME", f"{ha:.1f}h", f"{sa} sessions"),
        ]):
            cr = pygame.Rect(24 + i * (cw + 8), 94, cw, 88)
            rekt(self.screen, C.SURFACE, cr, radius=12, border=C.BORDER, bw=1)
            txt(self.screen, lbl, self.ftiny, C.DIM,   cr.x + 14, cr.y + 12, anchor='left')
            txt(self.screen, val, self.fmed,  C.WHITE, cr.x + 14, cr.y + 32, anchor='left')
            txt(self.screen, sub, self.ftiny, C.DIM,   cr.x + 14, cr.y + 64, anchor='left')

        txt(self.screen, "THIS WEEK", self.ftiny, C.DIM, 24, 202, anchor='left')
        pygame.draw.line(self.screen, C.BORDER, (24, 220), (W - 24, 220), 1)

        wd = self.stats.get_week()
        y  = 232
        if wd:
            for day in sorted(wd.keys()):
                dr = pygame.Rect(24, y, W - 48, 36)
                rekt(self.screen, C.SURFACE, dr, radius=8)
                txt(self.screen, str(day), self.fsmall, C.WHITE, dr.x + 14, dr.y + 9, anchor='left')
                detail = f"{wd[day]['hours']:.1f}h  ·  {wd[day]['sessions']} sessions"
                txt(self.screen, detail, self.fsmall, C.DIM, dr.right - 14, dr.y + 9, anchor='right')
                y += 46
        else:
            txt(self.screen, "No sessions this week", self.fsmall, C.DIM, cx, y + 10)

        back = pygame.Rect(cx - 80, H - 66, 160, 44)
        self.btns['back'] = back
        self._btn(back, "Back")

    def draw_tasks(self):
        W, H = self.screen.get_size()
        cx   = W // 2
        self.screen.fill(C.BG)
        self.btns = {}
        self.tbns = {}
        pygame.draw.rect(self.screen, C.RED, pygame.Rect(0, 0, W, 4))
        txt(self.screen, "Tasks", self.ftitle, C.WHITE, cx, 26)
        pygame.draw.line(self.screen, C.BORDER, (24, 78), (W - 24, 78), 1)

        all_tasks = self.tasks.list_all()
        y = 94
        if all_tasks:
            for tid, td in list(all_tasks.items())[:8]:
                done = td.get('completed', False)
                r    = pygame.Rect(24, y, W - 48, 46)
                self.tbns[tid] = r
                rekt(self.screen, C.SURFACE2 if done else C.SURFACE, r, radius=10, border=C.BORDER, bw=1)
                checkbox(self.screen, r.x + 22, r.y + 23, done)
                tc = C.DIM if done else C.WHITE
                txt(self.screen, td['title'], self.fsmall, tc, r.x + 44, r.y + 14, anchor='left')
                txt(self.screen, "DONE" if done else "TODO", self.ftiny,
                    C.GREEN if done else C.DIM, r.right - 12, r.y + 16, anchor='right')
                y += 56
        else:
            txt(self.screen, "No tasks yet", self.fbody, C.DIM, cx, 200)

        addr = pygame.Rect(24, y + 8, W - 48, 46)
        self.btns['add_task'] = addr
        self._btn(addr, "+ Add Task", ac=C.RED)

        back = pygame.Rect(cx - 80, H - 66, 160, 44)
        self.btns['back'] = back
        self._btn(back, "Back")

    def draw_presets(self):
        W, H = self.screen.get_size()
        cx   = W // 2
        self.screen.fill(C.BG)
        self.btns = {}
        self.pbns = {}
        pygame.draw.rect(self.screen, C.RED, pygame.Rect(0, 0, W, 4))
        txt(self.screen, "Presets", self.ftitle, C.WHITE, cx, 26)
        pygame.draw.line(self.screen, C.BORDER, (24, 78), (W - 24, 78), 1)

        ap = self.presets.list_all()
        y  = 94
        if ap:
            for name, s in list(ap.items())[:6]:
                r = pygame.Rect(24, y, W - 48, 56)
                self.pbns[name] = r
                rekt(self.screen, C.SURFACE, r, radius=12, border=C.BORDER, bw=1)
                txt(self.screen, name, self.fbody, C.WHITE, r.x + 16, r.y + 10, anchor='left')
                detail = f"{s['work_time']}m work  ·  {s['break_time']}m break  ·  {s.get('long_break', 15)}m long"
                txt(self.screen, detail, self.ftiny, C.DIM, r.x + 16, r.y + 34, anchor='left')
                txt(self.screen, "›", self.fbody, C.DIM, r.right - 18, r.y + 16, anchor='right')
                y += 66
        else:
            txt(self.screen, "No presets saved", self.fbody, C.DIM, cx, 200)

        back = pygame.Rect(cx - 80, H - 66, 160, 44)
        self.btns['back'] = back
        self._btn(back, "Back")

    def draw_settings(self):
        W, H = self.screen.get_size()
        cx   = W // 2
        self.screen.fill(C.BG)
        self.btns = {}
        pygame.draw.rect(self.screen, C.RED, pygame.Rect(0, 0, W, 4))
        txt(self.screen, "Settings", self.ftitle, C.WHITE, cx, 26)
        pygame.draw.line(self.screen, C.BORDER, (24, 78), (W - 24, 78), 1)

        music_on = self.config.get('music_enabled', True)
        sfx_on   = self.config.get('sound_enabled', True)
        goal     = self.config.get('daily_goal', 8)

        y = 94
        for lbl, sub, key, state in [
            ("Background Music", "Plays during work sessions", 'toggle_music', music_on),
            ("Sound Effects",    "Session start / complete",   'toggle_sfx',   sfx_on),
        ]:
            r = pygame.Rect(24, y, W - 48, 62)
            rekt(self.screen, C.SURFACE, r, radius=12, border=C.BORDER, bw=1)
            txt(self.screen, lbl, self.fbody, C.WHITE, r.x + 16, r.y + 12, anchor='left')
            txt(self.screen, sub, self.ftiny, C.DIM,   r.x + 16, r.y + 36, anchor='left')
            tc  = C.GREEN if state else C.SURFACE2
            tb  = C.GREEN if state else C.BORDER
            tr  = pygame.Rect(r.right - 86, r.y + 16, 70, 30)
            rekt(self.screen, tc, tr, radius=8, border=tb, bw=1)
            txt(self.screen, "ON" if state else "OFF", self.fsmall, C.WHITE,
                tr.x + tr.w // 2, tr.y + 6)
            self.btns[key] = tr
            y += 78

        gr = pygame.Rect(24, y, W - 48, 62)
        rekt(self.screen, C.SURFACE, gr, radius=12, border=C.BORDER, bw=1)
        txt(self.screen, "Daily Goal",         self.fbody, C.WHITE, gr.x + 16, gr.y + 12, anchor='left')
        txt(self.screen, f"Target: {goal}h/day", self.ftiny, C.DIM, gr.x + 16, gr.y + 36, anchor='left')
        mr  = pygame.Rect(gr.right - 114, gr.y + 16, 34, 30)
        vr  = pygame.Rect(gr.right - 74,  gr.y + 16, 28, 30)
        pr  = pygame.Rect(gr.right - 42,  gr.y + 16, 34, 30)
        for r2, lbl2 in [(mr, "−"), (pr, "+")]:
            rekt(self.screen, C.SURFACE2, r2, radius=7, border=C.BORDER, bw=1)
            txt(self.screen, lbl2, self.fbody, C.WHITE, r2.x + r2.w // 2, r2.y + 3)
        txt(self.screen, str(goal), self.fsmall, C.WHITE, vr.x + vr.w // 2, vr.y + 6)
        self.btns['goal_minus'] = mr
        self.btns['goal_plus']  = pr

        back = pygame.Rect(cx - 80, H - 66, 160, 44)
        self.btns['back'] = back
        self._btn(back, "Back")

    def handle_click(self, pos):
        for action, rect in self.btns.items():
            if not rect.collidepoint(pos):
                continue
            if action == 'start':
                self.launch()
            elif action in ('stats', 'tasks', 'presets', 'settings'):
                self.view = action
            elif action == 'back':
                self.view = 'main'
            elif action == 'add_task':
                tid = str(uuid.uuid4())[:8]
                self.tasks.add(tid, f"Task {len(self.tasks.list_all()) + 1}")
            elif action == 'toggle_music':
                val = not self.config.get('music_enabled', True)
                self.config['music_enabled'] = val
                Audio.set_music(val)
            elif action == 'toggle_sfx':
                val = not self.config.get('sound_enabled', True)
                self.config['sound_enabled'] = val
                Audio.set_sfx(val)
            elif action == 'goal_minus':
                self.config['daily_goal'] = max(1, self.config.get('daily_goal', 8) - 1)
            elif action == 'goal_plus':
                self.config['daily_goal'] = self.config.get('daily_goal', 8) + 1

        for tid, rect in self.tbns.items():
            if rect.collidepoint(pos):
                self.tasks.toggle(tid)

        for name, rect in self.pbns.items():
            if rect.collidepoint(pos):
                p = self.presets.get(name)
                if p:
                    self._launch_preset(p)

    def launch(self):
        t = PomodoroTimer(self.config, self.store, self.screen)
        t.start_session(
            self.config['work_time'],  self.config['break_time'],
            self.config['long_break'], self.config['sessions_until_long'],
            None, None, self.config.get('auto_continue', False)
        )
        self.screen = setup()
        self.view   = 'main'

    def _launch_preset(self, p):
        t = PomodoroTimer(self.config, self.store, self.screen)
        t.start_session(
            p['work_time'], p['break_time'], p['long_break'], p['sessions'],
            None, None, self.config.get('auto_continue', False)
        )
        self.screen = setup()
        self.view   = 'main'

    def run(self):
        views = {
            'main':     self.draw_main,
            'stats':    self.draw_stats,
            'tasks':    self.draw_tasks,
            'presets':  self.draw_presets,
            'settings': self.draw_settings,
        }
        while self.running:
            self.clock.tick(60)
            views.get(self.view, self.draw_main)()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_click(e.pos)
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE and self.view != 'main':
                        self.view = 'main'
            pygame.display.flip()
        pygame.quit()


def main():
    config  = Config()
    store   = DataStore('~/.pomodoro_data')
    presets = Presets()
    Menu(config, store, presets).run()


if __name__ == '__main__':
    main()