from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from contextcraft import __version__
from contextcraft.cli import app

runner = CliRunner()


def test_cli_execution_and_file_output(sample_repo: Path, tmp_path: Path) -> None:
    """Verify CLI flags (`--budget`, `--focus`, `--format`, `--output`, `--version`)."""
    # 1. Version flag
    ver_res = runner.invoke(app, ["--version"])
    assert ver_res.exit_code == 0
    assert __version__ in ver_res.stdout

    # 2. Compile to output file
    out_file = tmp_path / "compiled_context.md"
    cli_res = runner.invoke(
        app,
        [
            str(sample_repo),
            "--budget",
            "1.5k",
            "--focus",
            "UserClaims verify_token",
            "--output",
            str(out_file),
        ],
    )
    assert cli_res.exit_code == 0
    assert out_file.is_file()
    content = out_file.read_text(encoding="utf-8")
    assert "# Repository Context:" in content
    assert "sk-proj-1234567890" not in content

    # 3. Error exit code on invalid budget
    bad_res = runner.invoke(app, [str(sample_repo), "--budget", "invalid_budget"])
    assert bad_res.exit_code == 1


def test_cli_output_excludes_only_its_exact_path(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bundle.md").write_text("KEEP_NESTED_FILE")
    output = tmp_path / "bundle.md"
    output.write_text("DO_NOT_INGEST_OLD_OUTPUT")
    runner = CliRunner()

    version = runner.invoke(app, ["--version"])
    result = runner.invoke(
        app, [str(tmp_path), "--budget", "4k", "--output", str(output), "--quiet"]
    )

    assert version.exit_code == 0
    assert "0.2.0" in version.stdout
    assert result.exit_code == 0, result.output
    assert "DO_NOT_INGEST_OLD_OUTPUT" not in output.read_text()
    assert "KEEP_NESTED_FILE" in output.read_text()
    assert runner.invoke(app, [str(tmp_path), "--budget", "invalid"]).exit_code == 1
