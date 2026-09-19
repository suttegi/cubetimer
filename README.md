# cubetimer

A speedcubing timer that lives in your terminal. Scrambles, WCA averages, penalties and
session history — in one Python file with no dependencies.

```
scramble  R' L' B' R D2 F2 R2 L' F R' F' U R2 F2 R2 L2 F R B' R
ao5 9.84   ao12 10.42   best 7.91

   9.62  new PB!
```

## Install

Python 3.8+ is all you need. macOS and Linux ship it already.

```sh
git clone https://github.com/suttegi/cubetimer.git
cd cubetimer
./cubetimer.py
```

To run it from anywhere:

```sh
ln -s "$PWD/cubetimer.py" /usr/local/bin/cubetimer
```

## Use

Press `space` to start the timer, any key to stop. That is the whole loop.

| Key | Action |
| --- | --- |
| `space` | start / stop |
| `p` | toggle +2 on the last solve |
| `d` | toggle DNF on the last solve |
| `x` | delete the last solve |
| `s` | session stats |
| `h` | history (last 20) |
| `n` | new scramble |
| `?` | help |
| `q` | quit |

Options:

```sh
cubetimer -p 4x4            # 2x2, 3x3, 4x4 or 5x5 scrambles
cubetimer -s oh             # a separate session named "oh"
cubetimer -i 15             # 15 second WCA inspection
cubetimer --stats           # print stats and exit
cubetimer --history 50      # print the last 50 solves
cubetimer --sessions        # list every session
cubetimer --export oh.csv   # export a session to CSV
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
