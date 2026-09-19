#!/usr/bin/env python3
"""Tests for the statistics and scramble generator: python3 test_cubetimer.py"""

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("cubetimer", Path(__file__).with_name("cubetimer.py"))
ct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct)


def solves(*times):
    """Build solves from times; a string marks a penalty, e.g. ('10', 'DNF')."""
    out = []
    for t in times:
        if t == ct.DNF:
            out.append(ct.Solve(99.0, penalty=ct.DNF))
        elif isinstance(t, str) and t.endswith("+"):
            out.append(ct.Solve(float(t[:-1]), penalty="+2"))
        else:
            out.append(ct.Solve(float(t)))
    return out


class TestAverages(unittest.TestCase):
    def test_ao5_trims_best_and_worst(self):
        self.assertEqual(ct.average(solves(10, 12, 14, 16, 18), 5), 14.0)

    def test_ao5_needs_five_solves(self):
        self.assertIsNone(ct.average(solves(10, 12, 14), 5))

    def test_one_dnf_is_the_trimmed_worst(self):
        self.assertEqual(ct.average(solves(10, 12, 14, 16, ct.DNF), 5), 14.0)

    def test_two_dnfs_make_the_average_dnf(self):
        self.assertEqual(ct.average(solves(10, 12, 14, ct.DNF, ct.DNF), 5), ct.DNF)

    def test_ao12_trims_one_each_end(self):
        times = list(range(1, 13))  # 1..12 -> mean of 2..11
        self.assertAlmostEqual(ct.average(solves(*times), 12), 6.5)

    def test_ao100_trims_five_percent(self):
        times = list(range(1, 101))  # drop 5 lowest and 5 highest
        self.assertAlmostEqual(ct.average(solves(*times), 100), 50.5)

    def test_average_uses_the_latest_window(self):
        self.assertEqual(ct.average(solves(99, 99, 10, 12, 14, 16, 18), 5), 14.0)

    def test_mo3_is_dnf_when_any_solve_is(self):
        self.assertEqual(ct.mean_of(solves(10, 11, ct.DNF), 3), ct.DNF)

    def test_best_average_scans_the_session(self):
        # A slow start followed by a fast run: the best window is the fast one.
        session = solves(30, 30, 30, 30, 30, 10, 11, 12, 13, 14)
        self.assertAlmostEqual(ct.best_average(session, 5), 12.0)
        self.assertAlmostEqual(ct.average(session, 5), 12.0)


class TestPenalties(unittest.TestCase):
    def test_plus_two_adds_two_seconds(self):
        self.assertEqual(ct.Solve(10.0, penalty="+2").value, 12.0)

    def test_dnf_has_no_numeric_value(self):
        self.assertEqual(ct.Solve(10.0, penalty=ct.DNF).value, ct.DNF)

    def test_display_marks_a_penalty(self):
        self.assertEqual(ct.Solve(10.0, penalty="+2").display(), "12.00+")


class TestFormatting(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(ct.fmt(9.456), "9.46")

    def test_minutes(self):
        self.assertEqual(ct.fmt(83.4), "1:23.40")


class TestScramble(unittest.TestCase):
    def test_length(self):
        self.assertEqual(len(ct.scramble("3x3").split()), 20)
        self.assertEqual(len(ct.scramble("2x2").split()), 11)

    def test_no_face_repeats_back_to_back(self):
        for _ in range(200):
            faces = [m[0] for m in ct.scramble("3x3").split()]
            self.assertFalse(any(a == b for a, b in zip(faces, faces[1:])))

    def test_no_wasted_axis_sandwich(self):
        # R L R is really two moves, so it should never be generated.
        for _ in range(200):
            faces = [m[0] for m in ct.scramble("3x3").split()]
            for a, b, c in zip(faces, faces[1:], faces[2:]):
                self.assertFalse(ct.AXIS[a] == ct.AXIS[b] == ct.AXIS[c])


class TestRoundTrip(unittest.TestCase):
    def test_solve_survives_json(self):
        original = ct.Solve(12.34, "R U R'", "+2")
        copy = ct.Solve.from_dict(original.to_dict())
        self.assertEqual(copy.value, original.value)
        self.assertEqual(copy.scramble, "R U R'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
