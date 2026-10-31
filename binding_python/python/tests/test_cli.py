from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from contextcraft import TokenCounter
from contextcraft._cli import _write_output
from contextcraft.cli import main
from rich.markdown import Markdown


class CLITests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "main.py").write_text(
            "print('café 日本語')\n", encoding="utf-8", newline="\n"
        )

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "contextcraft", str(self.root), *arguments],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            env={**os.environ, "PYTHONUTF8": "1", "NO_COLOR": "1"},
        )

    def test_stdout_contains_only_artifact_and_summary_goes_to_stderr(self) -> None:
        result = self.run_cli("--format", "json")

        self.assertEqual(result.returncode, 0, result.stderr)
        artifact = json.loads(result.stdout)
        self.assertEqual(artifact["tree"], ["main.py"])
        self.assertEqual(artifact["files"][0]["content"], "print('café 日本語')\n")
        self.assertNotIn("compilation summary", result.stdout)
        self.assertIn("compilation summary", result.stderr)

    def test_quiet_suppresses_summary_without_suppressing_artifact(self) -> None:
        result = self.run_cli("--format", "json", "--quiet")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout)["tree"], ["main.py"])

    def test_budget_suffix_and_explicit_stdout(self) -> None:
        result = self.run_cli(
            "--format", "json", "--budget", "1k", "--output", "-", "--quiet"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["tree"], ["main.py"])
        self.assertLessEqual(TokenCounter().count(result.stdout), 1_000)
        self.assertFalse((self.root / "-").exists())

    def test_saved_output_is_utf8_and_excluded_on_repeated_runs(self) -> None:
        output = self.root / "context[1]{draft}.json"
        arguments = ("--format", "json", "--output", str(output), "--quiet")
        first = self.run_cli(*arguments)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = output.read_bytes()
        second = self.run_cli(*arguments)

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, "")
        self.assertEqual(second.stdout, "")
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(json.loads(original)["tree"], ["main.py"])
        self.assertIn("café 日本語".encode(), original)

    def test_exclusion_and_repeated_focus_options(self) -> None:
        (self.root / "ignored.txt").write_text("omit this", encoding="utf-8")
        result = self.run_cli(
            "--format",
            "json",
            "--exclude",
            "ignored.txt",
            "--focus-file",
            "main.py",
            "--focus-file",
            "*.py",
            "--quiet",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["tree"], ["main.py"])

    def test_invalid_arguments_exit_with_status_two(self) -> None:
        for arguments in [
            ("--budget", "0"),
            ("--budget", "invalid"),
            ("--format", "invalid"),
            ("--encoding", "invalid"),
            ("--unknown-option",),
        ]:
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr)

    def test_operational_errors_exit_with_status_one(self) -> None:
        for arguments in [
            ("--budget", "1"),
            ("--output", str(self.root)),
            ("--output", str(self.root / "missing" / "context.md")),
        ]:
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("error:", result.stderr)

    def test_console_script_entrypoint(self) -> None:
        executable = shutil.which("contextcraft")
        self.assertIsNotNone(executable)
        result = subprocess.run(
            [str(executable), str(self.root), "--format", "json", "--quiet"],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["tree"], ["main.py"])

    def test_missing_optional_dependencies_have_an_install_hint(self) -> None:
        with (
            patch.dict(sys.modules, {"cyclopts": None}),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            self.assertEqual(main([]), 1)
            self.assertIn("contextcraft-ai[cli]", stderr.getvalue())

    def test_markdown_is_rendered_on_a_terminal(self) -> None:
        content = '## "__init__.py" [FULL]\n\n```\nprint("hello")\n```\n'
        with (
            patch("contextcraft._cli.sys.stdout") as stdout,
            patch("contextcraft._cli.Console") as console,
        ):
            stdout.isatty.return_value = True
            _write_output(content, None, render_markdown=True)

            rendered = console.return_value.print.call_args.args[0]
            self.assertIsInstance(rendered, Markdown)
            self.assertEqual(rendered.markup, content)
            stdout.buffer.write.assert_not_called()

    def test_piped_and_saved_output_preserve_exact_bytes(self) -> None:
        content = '## "__init__.py" [FULL]\n\n```\ncafé\r\n日本語\n```\n'
        output = self.root / "artifact.md"
        _write_output(content, output, render_markdown=True)
        self.assertEqual(output.read_bytes(), content.encode("utf-8"))

        with patch("contextcraft._cli.sys.stdout") as stdout:
            stdout.isatty.return_value = False
            stdout.buffer = io.BytesIO()
            _write_output(content, None, render_markdown=True)
            self.assertEqual(stdout.buffer.getvalue(), content.encode("utf-8"))

        with patch("contextcraft._cli.sys.stdout", new_callable=io.StringIO) as stdout:
            _write_output(content, None, render_markdown=True)
            self.assertEqual(stdout.getvalue(), content)
