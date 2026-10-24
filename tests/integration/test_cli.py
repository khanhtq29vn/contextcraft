from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.utils import strip_ansi
from typer.testing import CliRunner

from contextcraft.cli import app
from contextcraft.elider import TokenCounter

runner = CliRunner()


def test_cli_writes_sanitized_context(sample_repo: Path, tmp_path: Path) -> None:
    output = tmp_path / "compiled_context.md"
    result = runner.invoke(
        app,
        [
            str(sample_repo),
            "--budget",
            "1.5k",
            "--focus",
            "UserClaims verify_token",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    content = output.read_text(encoding="utf-8")
    assert "# Repository Context:" in content
    assert "sk-proj-1234567890" not in content


def test_cli_rejects_invalid_budget(sample_repo: Path) -> None:
    result = runner.invoke(app, [str(sample_repo), "--budget", "invalid_budget"])

    assert result.exit_code == 1


def test_cli_output_excludes_only_its_exact_path(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bundle.md").write_text("KEEP_NESTED_FILE")
    output = tmp_path / "bundle.md"
    output.write_text("DO_NOT_INGEST_OLD_OUTPUT")

    result = runner.invoke(
        app, [str(tmp_path), "--budget", "4k", "--output", str(output), "--quiet"]
    )

    assert result.exit_code == 0, result.output
    content = output.read_text(encoding="utf-8")
    assert "DO_NOT_INGEST_OLD_OUTPUT" not in content
    assert "KEEP_NESTED_FILE" in content


def test_cli_encoding_flag_selects_tokenizer_encoding(sample_repo: Path, tmp_path: Path) -> None:
    """Verify `--encoding` / `-enc` is advertised and forwarded to token accounting."""
    help_res = runner.invoke(app, ["--help"])
    assert help_res.exit_code == 0
    help_text = strip_ansi(help_res.stdout)
    assert "--encoding" in help_text
    assert "-enc" in help_text

    observed: list[str] = []
    original_init = TokenCounter.__init__

    def recording_init(self: TokenCounter, encoding_name: str = "cl100k_base") -> None:
        observed.append(encoding_name)
        original_init(self, encoding_name)

    out_file = tmp_path / "compiled_o200k.md"
    with patch.object(TokenCounter, "__init__", recording_init):
        cli_res = runner.invoke(
            app,
            [
                str(sample_repo),
                "--budget",
                "2k",
                "-enc",
                "o200k_base",
                "--output",
                str(out_file),
                "--quiet",
            ],
        )
        default_res = runner.invoke(app, [str(sample_repo), "--budget", "2k", "--quiet"])

    assert cli_res.exit_code == 0
    assert default_res.exit_code == 0
    assert out_file.is_file()
    assert "o200k_base" in observed
    assert "cl100k_base" in observed


def test_cli_pin_full_keeps_files_full_and_warns_about_unmatched_patterns(tmp_path: Path) -> None:
    (tmp_path / "legacy.py").write_text(
        "".join(f"def legacy_{index}(value):\n    return value * {index}\n" for index in range(80))
    )
    for index in range(6):
        (tmp_path / f"module_{index}.py").write_text(
            f"def run_{index}(value):\n    return value + {index}\n"
        )
    output = tmp_path.parent / f"{tmp_path.name}_context.md"

    result = runner.invoke(
        app,
        [
            str(tmp_path),
            "--budget",
            "1400",
            "--pin-full",
            "legacy.py",
            "--pin-full",
            "missing.py",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "### `legacy.py` [FULL]" in output.read_text(encoding="utf-8")
    assert "'missing.py' matched no files" in strip_ansi(result.output)
    assert "--pin-full" in strip_ansi(runner.invoke(app, ["--help"]).stdout)


def test_cli_warns_about_pinned_files_that_cannot_stay_full_even_when_quiet(
    tmp_path: Path,
) -> None:
    (tmp_path / "legacy.py").write_text(
        "".join(f"def legacy_{index}(value):\n    return value * {index}\n" for index in range(80))
    )
    output = tmp_path.parent / f"{tmp_path.name}_context.md"

    result = runner.invoke(
        app,
        [str(tmp_path), "--budget", "600", "--pin-full", "legacy.py", "-q", "-o", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert "1 pinned file(s) did not fit the budget at FULL: legacy.py" in strip_ansi(result.output)


def test_cli_pin_warnings_escape_markup_and_skip_negations(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")
    output = tmp_path.parent / f"{tmp_path.name}_context.md"

    result = runner.invoke(
        app,
        [
            str(tmp_path),
            "--pin-full",
            "*.py",
            "--pin-full",
            "!free.py",
            "--pin-full",
            "src/[/x]",
            "-q",
            "-o",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    text = strip_ansi(result.output)
    assert "'src/[/x]' matched no files" in text
    assert "!free.py" not in text
