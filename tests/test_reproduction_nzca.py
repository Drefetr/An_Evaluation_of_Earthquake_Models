"""Small adversarial cohort/parser tests; full provider replay is a separate CLI."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "reproduction/nzca"
spec = importlib.util.spec_from_file_location("nzca_replay_tests", BUNDLE / "replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class TestReproductionNZCA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, _ = replay.load_manifest()
        cls.nz = replay.load_source("nzca_test_nz", "sources/nz_selection.py", cls.manifest)
        cls.parser = replay.load_source("nzca_test_ca_parser", "sources/ca_parser.py", cls.manifest)
        cls.ca = replay.load_source("nzca_test_ca", "sources/ca_selection.py", cls.manifest)

    def nz_row(self, **changes):
        row = dict(publicid="test", origintime="1960-01-01T00:00:00Z", magnitude="5",
                   depth="40", latitude="-48.5", longitude="165", magnitudetype="ML", eventtype="earthquake")
        row.update(changes)
        return row

    def ca_line(self, **changes):
        tokens = dict(date="1981/01/01", time="00:00:00.00", eventtype="eq", gtype="l", magnitude="4.00",
                      magtype="l", latitude="32.000", longitude="-121.000", depth="-5.0", quality="X+",
                      eventid="123", nph="10", ngrams="20")
        tokens.update(changes)
        return " ".join(tokens[name] for name in self.parser.FIELDS) + "\n"

    def test_nz_closed_spatial_and_magnitude_boundaries(self):
        selected, ledger, _ = self.nz.select_rows([self.nz_row(), self.nz_row(publicid="other", latitude="-33.5", longitude="180")])
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(row["included"] for row in ledger))

    def test_nz_unknown_depth_sentinel_is_excluded_but_other_negative_depth_retained(self):
        selected, ledger, _ = self.nz.select_rows([self.nz_row(depth="-9"), self.nz_row(publicid="negative", depth="-1")])
        self.assertEqual([row["event_id"] for row in selected], ["negative"])
        self.assertIn("unknown_depth_sentinel_minus_9", ledger[0]["all_reasons"])

    def test_nz_time_endpoint_is_exclusive(self):
        selected, ledger, _ = self.nz.select_rows([self.nz_row(origintime="2026-10-15T00:00:00Z")])
        self.assertEqual(selected, [])
        self.assertIn("outside_time_interval", ledger[0]["all_reasons"])

    def test_nz_nonfinite_and_invalid_clock_are_not_selected(self):
        selected, ledger, _ = self.nz.select_rows([self.nz_row(magnitude="NaN", origintime="bad")])
        self.assertEqual(selected, [])
        self.assertIn("invalid_or_missing_origin_time", ledger[0]["all_reasons"])
        self.assertIn("invalid_or_missing_magnitude", ledger[0]["all_reasons"])

    def test_nz_conflicting_duplicate_fails(self):
        with self.assertRaises(ValueError):
            self.nz.select_rows([self.nz_row(), self.nz_row(magnitude="5.1")])

    def test_nz_tied_events_are_not_jittered(self):
        selected, _, _ = self.nz.select_rows([self.nz_row(publicid="b"), self.nz_row(publicid="a")])
        self.assertEqual([r["event_id"] for r in selected], ["a", "b"])
        self.assertEqual(selected[0]["t_days"], selected[1]["t_days"])

    def test_ca_closed_boundaries_and_opaque_quality(self):
        row = self.parser.parse_structural_line(self.ca_line(latitude="37.000", longitude="-114.000", depth="40.0"))
        self.assertEqual(self.ca.in_population(row["original_tokens"]), "eligible_geometry")
        self.assertEqual(self.ca.validate_boundary_assignment("37.000", "-114.000"), (2, 2))
        self.assertEqual(row["quality"], "X+")

    def test_ca_missing_magnitude_is_not_zero_or_eligible(self):
        row = self.parser.parse_structural_line(self.ca_line(magtype="n"))
        self.assertEqual(self.ca.in_population(row["original_tokens"]), "excluded_magnitude_missing")

    def test_ca_malformed_date_and_field_count_fail(self):
        with self.assertRaises(self.parser.ParseError):
            self.parser.parse_structural_line(self.ca_line(date="1981/02/30"))
        with self.assertRaises(self.parser.ParseError):
            self.parser.parse_structural_line("1981/01/01 00:00:00 eq\n")

    def test_ca_exact_microseconds_and_fold_boundary(self):
        row = self.parser.parse_line(self.ca_line(date="2011/01/01", time="00:00:00.000001"))
        self.assertEqual(row["timestamp_us"] % 1_000_000, 1)
        self.assertEqual(row["classification"], "protected")
        row = self.parser.parse_line(self.ca_line(date="2026/01/01"))
        self.assertEqual(row["classification"], "outside_time")

    def run_small_lane(self, text):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw, output = root / "raw", root / "output"
            raw.mkdir(); output.mkdir()
            (raw / "1981.catalog").write_text(text, encoding="ascii")
            return self.ca.parse_lane(raw, [{"path":"1981.catalog"}], self.parser, "train", output)

    def test_ca_eligible_second_60_fails_instead_of_clamping(self):
        with self.assertRaises(self.ca.CustodyError) as caught:
            self.run_small_lane(self.ca_line(time="00:00:60.00"))
        self.assertEqual(caught.exception.code, "MODEL_CLOCK_UNAVAILABLE")

    def test_ca_conflicting_duplicate_fails(self):
        with self.assertRaises(self.ca.CustodyError):
            self.run_small_lane(self.ca_line() + self.ca_line(magnitude="4.10"))

    def test_ca_identical_duplicate_collapses_without_changing_source(self):
        events, _, _ = self.run_small_lane(self.ca_line() + self.ca_line())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source_line_1based"], 1)
        self.assertEqual(events[0]["source_tokens"]["quality"], "X+")

    def test_tampered_source_fails_hash_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input"
            path.write_bytes(b"altered")
            with self.assertRaisesRegex(replay.ReplayError, "input_hash_mismatch"):
                replay.checked_bytes(path, {"bytes":7,"sha256":replay.sha256(b"correct")})

    def test_manifest_paths_cannot_escape_or_use_windows_absolute_paths(self):
        for path in ("../escape", "/absolute", "C:/escape", "sub\\escape"):
            with self.subTest(path=path), self.assertRaises(replay.ReplayError):
                replay.safe_path(BUNDLE, path)

    def test_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            sentinel = Path(temporary) / "keep"
            sentinel.write_text("preserve", encoding="utf-8")
            self.assertEqual(replay.main(["--region","nz","--output",temporary]), 2)
            self.assertEqual(sentinel.read_text(), "preserve")

    def test_missing_downloaded_raw_records_failed_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "missing_raw"
            raw.mkdir()
            output = root / "new_output"
            self.assertEqual(replay.main(["--region","nz","--raw-input",str(raw),"--output",str(output)]), 1)
            receipt = json.loads((output / "result.json").read_text())
            self.assertFalse(receipt["passed"])
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["error"], "input_missing")


if __name__ == "__main__":
    unittest.main()
