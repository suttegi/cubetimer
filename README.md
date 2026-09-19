# cubetimer

A full-screen speedcubing timer that lives in your terminal. Scrambles, WCA averages,
penalties and session history — in one Python file with no dependencies.

```
 ╭─ scramble ───────────────────────────────────────────────────╮
 │        R F2 B' U2 B' L' B' D L R D' R2 D2 B' D2 U R2 L B L   │
 ╰──────────────────────────────────────────────────────────────╯
 ╭─ timer ──────────────────────────────────╮╭─ history ────────╮
 │                                          ││    1.      9.87  │
 │      ██████  ██████  ██████  ██████      ││    2.*     8.55  │
 │      ██  ██  ██  ██      ██  ██          ││    3.     10.02  │
 │      ██  ██  ██████  ██████  ██████      ││    4.      9.11  │
 │      ██  ██      ██      ██      ██      ││    5.      9.40+ │
 │      ██████  ██████  ██████  ██████      ││                  │
 │                                          ││                  │
 │           new personal best              ││                  │
 │      hold space, release to start        ││                  │
 ╰──────────────────────────────────────────╯│                  │
 ╭─ stats ──────────────────────────────────╮│                  │
 │ best         ao5          mo3            ││                  │
 │ 8.55         9.46         9.51           ││                  │
 ╰──────────────────────────────────────────╯╰──────────────────╯
```

The digits are tabular, so centiseconds never shift the layout while you solve.

Hold the space bar and the **15 second WCA inspection** counts down in big digits: green,
amber from 8 seconds, red once you are over. Release and the stopwatch starts. Going past
15 seconds gives the solve a +2, past 17 a DNF, exactly as it would at a competition.

## Install

Python 3.8+ is all you need. macOS and Linux ship it already.

```sh
git clone https://github.com/suttegi/cubetimer.git
cd cubetimer
./cubetimer.py
```

To run it from anywhere as `ct`, link it into a directory that is already on your `PATH`:

```sh
ln -s "$PWD/cubetimer.py" /opt/homebrew/bin/ct   # Apple silicon
ln -s "$PWD/cubetimer.py" /usr/local/bin/ct      # Intel macOS, Linux
```

It stays a symlink, so `git pull` updates the command too.

## Use

Hold `space` for inspection, release to start, press any key to stop. That is the loop.

| Key | Action |
| --- | --- |
| `space` | hold for inspection, release to start; any key stops |
| `↑` `↓` / `k` `j` | pick any solve in the history |
| `g` | jump back to the newest solve |
| `x` / `delete` | delete the picked solve |
| `p` | toggle +2 on the picked solve |
| `d` | toggle DNF on the picked solve |
| `i` | inspection countdown on / off |
| `n` | new scramble |
| `?` | keys overlay |
| `q` | quit |

Stats and history are always on screen, so there is nothing to open. Penalties and
deletions apply to whichever solve the history cursor is on, so fixing a mis-timed solve
from ten attempts ago takes two keys.

Options:

```sh
ct -p 4x4            # 2x2, 3x3, 4x4 or 5x5 scrambles
ct -s oh             # a separate session named "oh"
ct -I                # skip the inspection countdown
ct --stats           # print stats and exit
ct --history 50      # print the last 50 solves
ct --sessions        # list every session
ct --export oh.csv   # export a session to CSV
```

## Averages

Averages follow WCA rules, so the numbers match what you would get at a competition:

- **ao5 / ao12** — drop the best and the worst, mean the rest. A DNF counts as the worst
  time; two DNFs in the window make the whole average a DNF.
- **ao50 / ao100** — trim 5% from each end.
- **mo3** — plain mean of 3, where any DNF makes it a DNF.
- **best ao5 / ao12** — the best rolling average anywhere in the session.

## Data

Solves are stored as JSON in `~/.cubetimer/<session>.json`, one file per session, written
after every solve. Nothing leaves your machine. Point `CUBETIMER_HOME` somewhere else if
you want the files in another directory.

Each solve keeps its raw time, its scramble, any penalty and a timestamp, so `--export`
gives you a CSV you can take to a spreadsheet.

## Licence

MIT
