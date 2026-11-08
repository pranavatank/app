import io
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path

from tools import audit_repository_privacy as privacy
from tools.audit_repository_privacy import audit, private_path, read_secret


class PrivacyAuditTests(unittest.TestCase):
    def test_counts_secret_occurrences_without_disclosing_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "tracked.txt"
            fixture.write_bytes(b"first SYNTHETIC second SYNTHETIC")
            secret_hits, private_hits, failures = audit(root, [b"SYNTHETIC"], [fixture])
            self.assertEqual(secret_hits, [("tracked.txt", 2)])
            self.assertEqual(private_hits, [])
            self.assertEqual(failures, [])

    def test_binary_and_invalid_utf8_files_are_scanned_as_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "blob.bin"
            fixture.write_bytes(b"\xff\x00SYNTHETIC\xfe")
            secret_hits, _, _ = audit(root, [b"SYNTHETIC"], [fixture])
            self.assertEqual(secret_hits, [("blob.bin", 1)])

    def test_private_paths_are_detected_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(private_path(root / "Data" / "PersonalData" / "source.pdf", root))
            self.assertTrue(private_path(root / "data" / "financial.db", root))
            self.assertFalse(private_path(root / "docs" / "plan.md", root))
            self.assertFalse(private_path(root.parent / "data" / "data" / "outside.pdf", root))

    def test_tracked_private_lexical_path_is_flagged_before_symlink_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tracked_alias = root / "data" / "data" / "linked-source.pdf"
            # Model a tracked symlink whose resolved destination escapes the root.
            with patch.object(Path, "resolve", return_value=root.parent / "external-source.pdf"):
                self.assertTrue(private_path(tracked_alias, root))

    def test_unreadable_tracked_file_is_a_gate_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "tracked.bin"
            fixture.touch()
            with patch.object(Path, "read_bytes", side_effect=OSError("unreadable")):
                secret_hits, private_hits, failures = audit(root, [], [fixture])
            self.assertEqual(secret_hits, [])
            self.assertEqual(private_hits, [])
            self.assertEqual(failures, ["tracked.bin"])

    def test_read_secret_preserves_delimiters_inside_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "credentials.txt"
            path.write_text("AIS: VALUE:WITH=DELIMITERS\nEquitas=OTHER:VALUE\n", encoding="utf-8")
            self.assertEqual(read_secret(path), [b"VALUE:WITH=DELIMITERS", b"OTHER:VALUE"])

    def test_missing_or_empty_local_credentials_fail_closed(self):
        for contents in (None, "# no credential entries\n"):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as tmp:
                credential_file = Path(tmp) / "credentials.txt"
                if contents is not None:
                    credential_file.write_text(contents, encoding="utf-8")
                output = io.StringIO()
                with patch.object(privacy, "DEFAULT_SECRET_FILE", credential_file), \
                        patch.object(privacy, "ROOT", Path(tmp)), \
                        redirect_stdout(output):
                    status = privacy.main(["--check-local-secrets"])
                self.assertEqual(status, 1)
                self.assertIn("credentials.txt", output.getvalue())
                self.assertNotIn("no credential entries", output.getvalue())

    def test_default_mode_does_not_claim_secret_scan(self):
        output = io.StringIO()
        with patch.object(privacy, "ROOT", Path(".")), \
                patch.object(privacy, "audit", return_value=([], [], [])), \
                redirect_stdout(output):
            status = privacy.main([])
        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue().strip(), "tracked-path check passed; local secrets not checked")

    def test_cli_reports_only_path_and_count_for_secret_hit(self):
        output = io.StringIO()
        with patch.object(privacy, "ROOT", Path(".")), \
                patch.object(privacy, "read_secret", return_value=[b"SYNTHETIC"]), \
                patch.object(privacy, "audit", return_value=([("fixture.txt", 2)], [], [])), \
                redirect_stdout(output):
            status = privacy.main(["--check-local-secrets"])
        report = output.getvalue()
        self.assertEqual(status, 1)
        self.assertIn("fixture.txt (2)", report)
        self.assertNotIn("SYNTHETIC", report)


if __name__ == "__main__":
    unittest.main()
