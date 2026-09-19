#!/usr/bin/env python3
"""Speedcubing timer for the terminal: scrambles, WCA averages, persistent sessions."""

import argparse
import curses
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("CUBETIMER_HOME", Path.home() / ".cubetimer"))
DNF = "DNF"

FACES = ["U", "D", "L", "R", "F", "B"]
AXIS = {"U": 0, "D": 0, "L": 1, "R": 1, "F": 2, "B": 2}
SUFFIX = ["", "'", "2"]
SCRAMBLE_LEN = {"2x2": 11, "3x3": 20, "4x4": 40, "5x5": 60}

RELEASE_GAP = 0.12    # no key repeat for this long means the key came up
INSPECTION = 15.0     # WCA inspection; over it is +2, over the limit below is DNF
INSPECTION_DNF = 17.0


# --- solve model ---------------------------------------------------------


class Solve:
    def __init__(self, raw, scramble="", penalty="", stamp=None):
        self.raw = raw  # measured seconds, before penalty
        self.scramble = scramble
        self.penalty = penalty  # "", "+2" or "DNF"
        self.stamp = stamp or datetime.now().isoformat(timespec="seconds")

    @property
    def value(self):
        """Effective time: seconds, or DNF."""
        if self.penalty == DNF:
            return DNF
        return self.raw + 2 if self.penalty == "+2" else self.raw

    def display(self):
        if self.penalty == DNF:
            return "DNF"
        text = fmt(self.value)
        return text + "+" if self.penalty == "+2" else text

    def to_dict(self):
        return {
            "raw": self.raw,
            "scramble": self.scramble,
            "penalty": self.penalty,
            "stamp": self.stamp,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d["raw"], d.get("scramble", ""), d.get("penalty", ""), d.get("stamp"))


def fmt(seconds):
    if seconds == DNF:
        return "DNF"
    if seconds >= 60:
        minutes, rest = divmod(seconds, 60)
        return f"{int(minutes)}:{rest:05.2f}"
    return f"{seconds:.2f}"


def fmt_or_dash(value):
    if value is None:
        return "—"
    return fmt(value) if value != DNF else "DNF"


# --- statistics ----------------------------------------------------------


def average(solves, count):
    """WCA average of `count`: trim 5% (at least one) from each end, mean the rest."""
    if len(solves) < count:
        return None
    window = [s.value for s in solves[-count:]]
    trim = max(1, round(count * 0.05))
    dnfs = sum(1 for v in window if v == DNF)
    if dnfs > trim:
        return DNF
    finite = sorted(v for v in window if v != DNF)
    # DNFs always sit at the slow end, so they consume trims from the top.
    top_trim = trim - dnfs
    kept = finite[trim:len(finite) - top_trim] if top_trim else finite[trim:]
    return sum(kept) / len(kept) if kept else DNF


def mean_of(solves, count):
    """Plain mean; a single DNF makes it a DNF."""
    if len(solves) < count:
        return None
    window = [s.value for s in solves[-count:]]
    if any(v == DNF for v in window):
        return DNF
    return sum(window) / len(window)


def best_average(solves, count):
    """Best rolling average of `count` across the whole session."""
    if len(solves) < count:
        return None
    best = None
    for end in range(count, len(solves) + 1):
        avg = average(solves[:end], count)
        if avg == DNF or avg is None:
            continue
        if best is None or avg < best:
            best = avg
    return best if best is not None else DNF


def session_stats(solves):
    done = [s for s in solves if s.value != DNF]
    times = [s.value for s in done]
    return {
        "count": len(solves),
        "solved": len(done),
        "best": min(times) if times else None,
        "worst": max(times) if times else None,
        "mean": sum(times) / len(times) if times else None,
        "mo3": mean_of(solves, 3),
        "ao5": average(solves, 5),
        "ao12": average(solves, 12),
        "ao50": average(solves, 50),
        "ao100": average(solves, 100),
        "best_ao5": best_average(solves, 5),
        "best_ao12": best_average(solves, 12),
    }


# --- scrambles -----------------------------------------------------------


def scramble(puzzle="3x3"):
    length = SCRAMBLE_LEN.get(puzzle, 20)
    wide = puzzle in ("4x4", "5x5")
    moves, last_face, last_axis = [], None, None
    while len(moves) < length:
        face = random.choice(FACES)
        if face == last_face:
            continue
        # Avoid A B A on one axis, which collapses to two moves.
        if AXIS[face] == last_axis and len(moves) >= 2 and moves[-2][0] in AXIS:
            if AXIS[moves[-2][0]] == AXIS[face]:
                continue
        token = face
        if wide and random.random() < 0.35:
            token += "w"
        moves.append(token + random.choice(SUFFIX))
        last_face, last_axis = face, AXIS[face]
    return " ".join(moves)


# --- storage -------------------------------------------------------------


def session_path(name):
    return DATA_DIR / f"{name}.json"


def load(name):
    path = session_path(name)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return [Solve.from_dict(d) for d in raw]


def save(name, solves):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = session_path(name).with_suffix(".tmp")
    tmp.write_text(json.dumps([s.to_dict() for s in solves], indent=1))
    tmp.replace(session_path(name))


# --- big digits ----------------------------------------------------------

# 5-row glyphs. Every glyph is the same width so centiseconds never shift the
# layout while the timer runs.
GLYPHS = {
    "0": ["███", "█ █", "█ █", "█ █", "███"],
    "1": ["  █", "  █", "  █", "  █", "  █"],
    "2": ["███", "  █", "███", "█  ", "███"],
    "3": ["███", "  █", "███", "  █", "███"],
    "4": ["█ █", "█ █", "███", "  █", "  █"],
    "5": ["███", "█  ", "███", "  █", "███"],
    "6": ["███", "█  ", "███", "█ █", "███"],
    "7": ["███", "  █", "  █", "  █", "  █"],
    "8": ["███", "█ █", "███", "█ █", "███"],
    "9": ["███", "█ █", "███", "  █", "███"],
    ".": ["   ", "   ", "   ", "   ", " █ "],
    ":": ["   ", " █ ", "   ", " █ ", "   "],
    "+": ["   ", " █ ", "███", " █ ", "   "],
    "D": ["██ ", "█ █", "█ █", "█ █", "██ "],
    "N": ["█ █", "███", "███", "█ █", "█ █"],
    "F": ["███", "█  ", "██ ", "█  ", "█  "],
    " ": ["   ", "   ", "   ", "   ", "   "],
}


def big(text, scale=2):
    """Render text as 5 rows of block glyphs, each cell widened `scale` times."""
    rows = []
    for row in range(5):
        parts = []
        for char in text:
            glyph = GLYPHS.get(char, GLYPHS[" "])[row]
            parts.append("".join(c * scale for c in glyph))
        rows.append("  ".join(parts))
    return rows


# --- curses UI -----------------------------------------------------------

C_DIM = 1
C_ACCENT = 2
C_GOOD = 3
C_WARN = 4
C_BAD = 5
C_TITLE = 6


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_DIM, curses.COLOR_WHITE, -1)
    curses.init_pair(C_ACCENT, curses.COLOR_CYAN, -1)
    curses.init_pair(C_GOOD, curses.COLOR_GREEN, -1)
    curses.init_pair(C_WARN, curses.COLOR_YELLOW, -1)
    curses.init_pair(C_BAD, curses.COLOR_RED, -1)
    curses.init_pair(C_TITLE, curses.COLOR_MAGENTA, -1)


def box(win, top, left, height, width, title="", color=C_DIM):
    """Draw a rounded panel with a title."""
    attr = curses.color_pair(color)
    try:
        win.addstr(top, left, "╭" + "─" * (width - 2) + "╮", attr)
        for row in range(1, height - 1):
            win.addstr(top + row, left, "│", attr)
            win.addstr(top + row, left + width - 1, "│", attr)
        win.addstr(top + height - 1, left, "╰" + "─" * (width - 2) + "╯", attr)
        if title:
            win.addstr(top, left + 2, f" {title} ", curses.color_pair(C_TITLE) | curses.A_BOLD)
    except curses.error:
        pass  # a panel that does not fit is simply clipped


def put(win, row, col, text, attr=0):
    try:
        win.addstr(row, col, text, attr)
    except curses.error:
        pass


def centre(win, row, width, text, attr=0, left=0):
    put(win, row, left + max(0, (width - len(text)) // 2), text, attr)


def wrap(text, width):
    words, lines, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines


class App:
    def __init__(self, screen, args):
        self.screen = screen
        self.args = args
        self.solves = load(args.session)
        self.scramble = scramble(args.puzzle)
        self.state = "idle"        # idle | inspect | running
        self.inspect_since = 0.0
        self.last_space = 0.0
        self.started = 0.0
        self.message = ""
        self.show_help = False
        self.inspection = not args.no_inspection
        self.cursor = None         # index into self.solves; None follows the newest

    # -- state machine ---------------------------------------------------

    def on_space(self, now):
        if self.state == "running":
            self.stop(now)
        elif self.state == "idle":
            self.state = "inspect"
            self.inspect_since = now
            self.last_space = now
            self.message = ""
        else:  # key repeat while the bar is still down
            self.last_space = now

    def tick(self, now):
        """Space came up when the key repeat stops."""
        if self.state == "inspect" and now - self.last_space >= RELEASE_GAP:
            self.start(now)

    def inspection_penalty(self, now):
        """WCA: over 15s is +2, over 17s is a DNF."""
        if not self.inspection:
            return ""
        used = now - self.inspect_since
        if used > INSPECTION_DNF:
            return DNF
        return "+2" if used > INSPECTION else ""

    def start(self, now):
        self.pending_penalty = self.inspection_penalty(now)
        self.state = "running"
        self.started = now

    def stop(self, now):
        self.state = "idle"
        solve = Solve(now - self.started, self.scramble, self.pending_penalty)
        self.solves.append(solve)
        self.cursor = None
        save(self.args.session, self.solves)
        st = session_stats(self.solves)
        if self.pending_penalty:
            self.message = f"inspection {self.pending_penalty}"
        elif st["best"] is not None and abs(solve.value - st["best"]) < 1e-9 and len(self.solves) > 1:
            self.message = "new personal best"
        else:
            self.message = ""
        self.scramble = scramble(self.args.puzzle)

    # -- selection -------------------------------------------------------

    @property
    def selected(self):
        """Index of the solve the keys act on: the cursor, else the newest."""
        if not self.solves:
            return None
        return len(self.solves) - 1 if self.cursor is None else self.cursor

    def move_cursor(self, step):
        if not self.solves:
            return
        self.cursor = min(max((self.selected or 0) + step, 0), len(self.solves) - 1)
        if self.cursor == len(self.solves) - 1:
            self.cursor = None  # snap back to following the newest solve

    # -- drawing ---------------------------------------------------------

    def timer_text(self, now):
        if self.state == "running":
            return fmt(now - self.started)
        if self.state == "inspect":
            if not self.inspection:
                return "0.00"
            left = INSPECTION - (now - self.inspect_since)
            return f"{max(left, 0):.0f}" if left > -2 else "DNF"
        if self.solves:
            return self.solves[self.selected].display()
        return "0.00"

    def timer_colour(self):
        if self.state == "running":
            return C_ACCENT
        if self.state == "inspect":
            if not self.inspection:
                return C_GOOD
            used = time.monotonic() - self.inspect_since
            if used > INSPECTION_DNF:
                return C_BAD
            return C_WARN if used > INSPECTION - 7 else C_GOOD
        return C_DIM

    def draw(self, now):
        screen = self.screen
        screen.erase()
        height, width = screen.getmaxyx()
        if height < 18 or width < 62:
            put(screen, 0, 0, "Window too small — make it at least 62x18.", curses.color_pair(C_BAD))
            screen.refresh()
            return

        st = session_stats(self.solves)

        # header
        head = f" cubetimer   {self.args.puzzle}   session: {self.args.session} "
        put(screen, 0, 2, head, curses.color_pair(C_TITLE) | curses.A_BOLD)
        hint = "? help   q quit "
        put(screen, 0, width - len(hint) - 2, hint, curses.color_pair(C_DIM) | curses.A_DIM)

        # scramble panel
        lines = wrap(self.scramble, width - 8)[:2]
        box(screen, 1, 1, len(lines) + 2, width - 2, "scramble", C_ACCENT)
        for i, line in enumerate(lines):
            centre(screen, 2 + i, width - 2, line, curses.color_pair(C_ACCENT) | curses.A_BOLD, 1)

        top = 3 + len(lines)
        side = 30 if width >= 96 else 0          # history column only on wide terminals
        main_w = width - 2 - side

        # timer panel
        timer_h = height - top - 9
        box(screen, top, 1, timer_h, main_w, "timer", self.timer_colour())
        scale = 2 if main_w >= 52 else 1
        digits = big(self.timer_text(now), scale)
        first = top + max(1, (timer_h - 5) // 2)
        colour = curses.color_pair(self.timer_colour()) | curses.A_BOLD
        for i, row in enumerate(digits):
            if first + i < top + timer_h - 1:
                centre(screen, first + i, main_w, row, colour, 1)

        if self.state == "inspect" and self.inspection:
            used = now - self.inspect_since
            status = ("inspection — release to start" if used <= INSPECTION else
                      "over 15s: +2" if used <= INSPECTION_DNF else "over 17s: DNF")
        else:
            status = {
                "idle": "hold space for inspection, release to start",
                "inspect": "release to start",
                "running": "press any key to stop",
            }[self.state]
        centre(screen, top + timer_h - 2, main_w, status,
               curses.color_pair(self.timer_colour()) | curses.A_DIM, 1)
        if self.message:
            centre(screen, first + 6, main_w, self.message,
                   curses.color_pair(C_GOOD) | curses.A_BOLD, 1)

        # stats panel
        stats_top = top + timer_h
        box(screen, stats_top, 1, 8, main_w, "stats", C_DIM)
        col = main_w // 3
        cells = [
            ("best", fmt_or_dash(st["best"])), ("ao5", fmt_or_dash(st["ao5"])),
            ("mo3", fmt_or_dash(st["mo3"])),
            ("worst", fmt_or_dash(st["worst"])), ("ao12", fmt_or_dash(st["ao12"])),
            ("ao50", fmt_or_dash(st["ao50"])),
            ("mean", fmt_or_dash(st["mean"])), ("best ao5", fmt_or_dash(st["best_ao5"])),
            ("best ao12", fmt_or_dash(st["best_ao12"])),
        ]
        for i, (label, value) in enumerate(cells):
            row = stats_top + 1 + i // 3 * 2
            left = 3 + (i % 3) * col
            put(screen, row, left, f"{label:<10}", curses.color_pair(C_DIM) | curses.A_DIM)
            put(screen, row + 1, left, f"{value:<10}", curses.color_pair(C_GOOD) | curses.A_BOLD)
        put(screen, stats_top + 6, 3,
            f"{st['solved']}/{st['count']} solved",
            curses.color_pair(C_DIM) | curses.A_DIM)

        # history column
        if side:
            rows = height - top - 3
            box(screen, top, width - side - 1, height - top - 1, side,
                "history  ↑↓ select", C_DIM)
            best = st["best"]
            chosen = self.selected
            # Keep the selected solve in view while scrolling through a long session.
            end = min(len(self.solves), max(chosen + 1, rows)) if chosen is not None else 0
            start = max(0, end - rows)
            for i, index in enumerate(range(start, end)):
                solve = self.solves[index]
                mark = "*" if best is not None and solve.value == best else " "
                if index == chosen:
                    attr = curses.color_pair(C_ACCENT) | curses.A_REVERSE | curses.A_BOLD
                elif mark == "*":
                    attr = curses.color_pair(C_GOOD)
                else:
                    attr = curses.color_pair(C_DIM)
                put(screen, top + 1 + i, width - side + 1,
                    f"{index + 1:>4}.{mark}{solve.display():>9} ", attr)

        if self.show_help:
            self.draw_help(height, width)
        screen.refresh()

    def draw_help(self, height, width):
        rows = [
            ("space", "hold for inspection, release to start; any key stops"),
            ("↑ ↓ / k j", "pick a solve in the history"),
            ("g", "jump back to the newest solve"),
            ("x / del", "delete the picked solve"),
            ("p", "toggle +2 on the picked solve"),
            ("d", "toggle DNF on the picked solve"),
            ("i", "inspection countdown on / off"),
            ("n", "new scramble"),
            ("?", "close this help"),
            ("q", "quit"),
        ]
        w, h = 60, len(rows) + 4
        top, left = (height - h) // 2, (width - w) // 2
        for row in range(h):  # clear the area behind the panel
            put(self.screen, top + row, left, " " * w)
        box(self.screen, top, left, h, w, "keys", C_TITLE)
        for i, (key, text) in enumerate(rows):
            put(self.screen, top + 2 + i, left + 3, f"{key:<11}",
                curses.color_pair(C_ACCENT) | curses.A_BOLD)
            put(self.screen, top + 2 + i, left + 15, text, curses.color_pair(C_DIM))

    # -- input -----------------------------------------------------------

    def handle(self, key, now):
        if self.state == "running":
            self.stop(now)
            return True
        if key == ord(" "):
            self.on_space(now)
        elif key in (ord("q"), 27):
            return False
        elif key == ord("?"):
            self.show_help = not self.show_help
        elif key in (curses.KEY_UP, ord("k")):
            self.cursor = None if not self.solves else max((self.selected or 0) - 1, 0)
        elif key in (curses.KEY_DOWN, ord("j")):
            self.move_cursor(1)
        elif key == ord("g"):
            self.cursor = None
        elif key == ord("i"):
            self.inspection = not self.inspection
            self.message = f"inspection {'on' if self.inspection else 'off'}"
        elif key in (ord("p"), ord("d")) and self.solves:
            want = "+2" if key == ord("p") else DNF
            solve = self.solves[self.selected]
            solve.penalty = "" if solve.penalty == want else want
            save(self.args.session, self.solves)
            self.message = f"#{self.selected + 1} → {solve.display()}"
        elif key in (ord("x"), curses.KEY_DC, curses.KEY_BACKSPACE, 127) and self.solves:
            index = self.selected
            gone = self.solves.pop(index)
            self.cursor = None if index >= len(self.solves) else index
            save(self.args.session, self.solves)
            self.message = f"deleted #{index + 1}  {gone.display()}"
        elif key == ord("n"):
            self.scramble = scramble(self.args.puzzle)
        return True

    def run(self):
        curses.curs_set(0)
        self.screen.nodelay(True)
        init_colors()
        while True:
            now = time.monotonic()
            key = self.screen.getch()
            if key != -1:
                if key == curses.KEY_RESIZE:
                    continue
                if not self.handle(key, now):
                    return
            self.tick(now)
            self.draw(now)
            time.sleep(0.01)


# --- plain-text views (for the non-interactive flags) --------------------


def print_stats(solves):
    st = session_stats(solves)
    if not st["count"]:
        print("No solves yet.")
        return
    print(f"\nSession  {st['solved']}/{st['count']} solved")
    for label, key in [("best", "best"), ("worst", "worst"), ("mean", "mean"),
                       ("mo3", "mo3"), ("ao5", "ao5"), ("ao12", "ao12"),
                       ("ao50", "ao50"), ("ao100", "ao100"),
                       ("best ao5", "best_ao5"), ("best ao12", "best_ao12")]:
        print(f"  {label:<10}{fmt_or_dash(st[key]):>10}")
    print()


def print_history(solves, limit=20):
    if not solves:
        print("No solves yet.")
        return
    best = min((s.value for s in solves if s.value != DNF), default=None)
    for i, s in enumerate(solves[max(0, len(solves) - limit):], max(1, len(solves) - limit + 1)):
        mark = " PB" if s.value == best and best is not None else "   "
        print(f"{i:>4}. {s.display():>9}{mark}  {s.scramble}")


# --- entry point ---------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Speedcubing timer for the terminal.")
    parser.add_argument("-s", "--session", default="default", help="session name")
    parser.add_argument("-p", "--puzzle", default="3x3", choices=sorted(SCRAMBLE_LEN),
                        help="puzzle type (scramble length)")
    parser.add_argument("-I", "--no-inspection", action="store_true",
                        help="skip the 15 second inspection countdown")
    parser.add_argument("--stats", action="store_true", help="print stats and exit")
    parser.add_argument("--history", type=int, nargs="?", const=20, metavar="N",
                        help="print the last N solves and exit")
    parser.add_argument("--sessions", action="store_true", help="list sessions and exit")
    parser.add_argument("--export", metavar="FILE", help="write the session to CSV and exit")
    args = parser.parse_args()

    if args.sessions:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        for path in sorted(DATA_DIR.glob("*.json")):
            st = session_stats(load(path.stem))
            print(f"{path.stem:<16}{st['count']:>4} solves   best {fmt_or_dash(st['best'])}")
        return

    if args.stats:
        print_stats(load(args.session))
        return

    if args.history is not None:
        print_history(load(args.session), args.history)
        return

    if args.export:
        solves = load(args.session)
        with open(args.export, "w") as fh:
            fh.write("n,time,penalty,scramble,timestamp\n")
            for i, s in enumerate(solves, 1):
                fh.write(f"{i},{s.raw:.3f},{s.penalty},{s.scramble},{s.stamp}\n")
        print(f"wrote {len(solves)} solves to {args.export}")
        return

    if not sys.stdin.isatty():
        print("cubetimer needs an interactive terminal.")
        sys.exit(1)
    curses.wrapper(lambda screen: App(screen, args).run())


if __name__ == "__main__":
    main()
