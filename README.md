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

The digits are tabular, so centiseconds never shift the layout while you solve. The panel
turns red while you hold the space bar and green the moment the timer is armed, the way a
proper cubing timer behaves.

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

Hold `space`, release to start, press any key to stop. That is the whole loop.

| Key | Action |
| --- | --- |
| `space` | hold, release to start; any key stops |
| `p` | toggle +2 on the last solve |
| `d` | toggle DNF on the last solve |
| `x` | delete the last solve |
| `n` | new scramble |
| `?` | keys overlay |
| `q` | quit |

Stats and history are always on screen, so there is nothing to open.

Options:

```sh
ct -p 4x4            # 2x2, 3x3, 4x4 or 5x5 scrambles
ct -s oh             # a separate session named "oh"
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
