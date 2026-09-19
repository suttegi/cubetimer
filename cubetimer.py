#!/usr/bin/env python3
"""Speedcubing timer for the terminal: scrambles, WCA averages, persistent sessions."""

import argparse
import json
import os
import random
import select
import sys
import termios
import time
import tty
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("CUBETIMER_HOME", Path.home() / ".cubetimer"))
DNF = "DNF"

FACES = ["U", "D", "L", "R", "F", "B"]
AXIS = {"U": 0, "D": 0, "L": 1, "R": 1, "F": 2, "B": 2}
SUFFIX = ["", "'", "2"]
SCRAMBLE_LEN = {"2x2": 11, "3x3": 20, "4x4": 40, "5x5": 60}

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"


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
    except (json.JSONDecodeError, OSError) as exc:
        print(f"{RED}Cannot read {path}: {exc}{RESET}")
        return []
    return [Solve.from_dict(d) for d in raw]


def save(name, solves):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = session_path(name).with_suffix(".tmp")
    tmp.write_text(json.dumps([s.to_dict() for s in solves], indent=1))
    tmp.replace(session_path(name))


# --- terminal ------------------------------------------------------------


class RawKeys:
    """Read single keypresses without echo."""

    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, *_):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
        print("\033[?25h", end="", flush=True)  # cursor back on

    def read(self):
        return sys.stdin.read(1)


def run_timer(inspection):
    """Runs one solve: optional inspection, then timing. None if cancelled."""
    keys = RawKeys.instance
    if inspection:
        start = time.monotonic()
        print(f"{YELLOW}Inspection — space to start, q to cancel{RESET}")
        while True:
            left = inspection - (time.monotonic() - start)
            if left <= 0:
                print(f"\r{RED}Inspection over!{RESET}          ")
                break
            print(f"\r{YELLOW}{left:4.1f}{RESET} ", end="", flush=True)
            if select_key(0.05):
                key = keys.read()
                if key == "q":
                    print("\r cancelled        ")
                    return None
                break
        print()

    if inspection:  # after inspection the space is a fresh, deliberate start
        print(f"{DIM}press space to start{RESET}", end="", flush=True)
        while keys.read() != " ":
            pass
    print(f"\r\033[K{GREEN}GO{RESET}", flush=True)
    print("\033[?25l", end="")  # hide cursor while running

    start = time.monotonic()
    while not select_key(0.01):
        print(f"\r{BOLD}{time.monotonic() - start:7.2f}{RESET}", end="", flush=True)
    keys.read()
    elapsed = time.monotonic() - start
    print("\033[?25h", end="")
    print(f"\r\033[K", end="")
    return elapsed


def select_key(timeout):
    return bool(select.select([sys.stdin], [], [], timeout)[0])


# --- views ---------------------------------------------------------------


def line(label, value, width=10):
    text = fmt(value) if isinstance(value, float) else (value or "—")
    return f"{DIM}{label:<10}{RESET}{text:>{width}}"


def show_stats(solves):
    st = session_stats(solves)
    if not st["count"]:
        print(f"{DIM}No solves yet.{RESET}")
        return
    print(f"\n{BOLD}Session{RESET}  {st['solved']}/{st['count']} solved")
    print(line("best", st["best"]), "  ", line("worst", st["worst"]))
    print(line("mean", st["mean"]), "  ", line("mo3", st["mo3"]))
    print(line("ao5", st["ao5"]), "  ", line("ao12", st["ao12"]))
    print(line("ao50", st["ao50"]), "  ", line("ao100", st["ao100"]))
    print(line("best ao5", st["best_ao5"]), "  ", line("best ao12", st["best_ao12"]))
    print()


def show_history(solves, limit=20):
    if not solves:
        print(f"{DIM}No solves yet.{RESET}")
        return
    print()
    start = max(0, len(solves) - limit)
    best = min((s.value for s in solves if s.value != DNF), default=None)
    for i, s in enumerate(solves[start:], start + 1):
        mark = f" {GREEN}PB{RESET}" if s.value == best and best is not None else ""
        stamp = s.stamp.split("T")[1] if "T" in s.stamp else ""
        print(f"{i:>4}. {s.display():>9}{mark}  {DIM}{stamp}  {s.scramble}{RESET}")
    print()


def show_help():
    print(f"""
{BOLD}Keys{RESET}
  {CYAN}space{RESET}  start / stop the timer
  {CYAN}p{RESET}      toggle +2 on the last solve
  {CYAN}d{RESET}      toggle DNF on the last solve
  {CYAN}x{RESET}      delete the last solve
  {CYAN}s{RESET}      session stats
  {CYAN}h{RESET}      history (last 20)
  {CYAN}n{RESET}      new scramble
  {CYAN}?{RESET}      this help
  {CYAN}q{RESET}      quit
""")


# --- main loop -----------------------------------------------------------


def interactive(args):
    solves = load(args.session)
    print(f"{BOLD}cubetimer{RESET}  session {CYAN}{args.session}{RESET} · {args.puzzle}"
          f" · {len(solves)} solve(s) loaded")
    show_help()
    current = scramble(args.puzzle)

    with RawKeys() as keys:
        RawKeys.instance = keys
        while True:
            print(f"{BOLD}scramble{RESET}  {current}")
            st = session_stats(solves)
            if st["ao5"] is not None:
                print(f"{DIM}ao5 {fmt(st['ao5']) if st['ao5'] != DNF else 'DNF'}"
                      f"   ao12 {fmt(st['ao12']) if st['ao12'] not in (None, DNF) else '—'}"
                      f"   best {fmt(st['best']) if st['best'] else '—'}{RESET}")
            key = keys.read()

            if key == " ":
                elapsed = run_timer(args.inspection)
                if elapsed is None:
                    continue
                solve = Solve(elapsed, current)
                solves.append(solve)
                save(args.session, solves)
                st = session_stats(solves)
                flag = ""
                if st["best"] is not None and abs(solve.value - st["best"]) < 1e-9:
                    flag = f"  {GREEN}new PB!{RESET}"
                print(f"{BOLD}{solve.display()}{RESET}{flag}")
                if st["ao5"] not in (None, DNF):
                    print(f"{DIM}ao5 {fmt(st['ao5'])}{RESET}")
                current = scramble(args.puzzle)
            elif key in ("p", "d") and solves:
                want = "+2" if key == "p" else DNF
                last = solves[-1]
                last.penalty = "" if last.penalty == want else want
                save(args.session, solves)
                print(f"last → {BOLD}{last.display()}{RESET}")
            elif key == "x" and solves:
                gone = solves.pop()
                save(args.session, solves)
                print(f"{RED}deleted{RESET} {gone.display()}")
            elif key == "s":
                show_stats(solves)
            elif key == "h":
                show_history(solves)
            elif key == "n":
                current = scramble(args.puzzle)
            elif key == "?":
                show_help()
            elif key in ("q", "\x03", "\x04"):
                print("bye")
                return


def main():
    parser = argparse.ArgumentParser(description="Speedcubing timer for the terminal.")
    parser.add_argument("-s", "--session", default="default", help="session name")
    parser.add_argument("-p", "--puzzle", default="3x3", choices=sorted(SCRAMBLE_LEN),
                        help="puzzle type (scramble length)")
    parser.add_argument("-i", "--inspection", type=float, default=0, metavar="SEC",
                        help="inspection countdown before each solve, e.g. 15")
    parser.add_argument("--stats", action="store_true", help="print stats and exit")
    parser.add_argument("--history", type=int, nargs="?", const=20, metavar="N",
                        help="print the last N solves and exit")
    parser.add_argument("--sessions", action="store_true", help="list sessions and exit")
    parser.add_argument("--export", metavar="FILE", help="write the session to CSV and exit")
    args = parser.parse_args()

    if args.sessions:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        for path in sorted(DATA_DIR.glob("*.json")):
            solves = load(path.stem)
            st = session_stats(solves)
            best = fmt(st["best"]) if st["best"] else "—"
            print(f"{path.stem:<16}{st['count']:>4} solves   best {best}")
        return

    if args.stats:
        show_stats(load(args.session))
        return

    if args.history is not None:
        show_history(load(args.session), args.history)
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
    try:
        interactive(args)
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
