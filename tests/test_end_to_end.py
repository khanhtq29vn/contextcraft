"""End-to-end integration tests for the `ContextCraft` SDK and `typer` CLI."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from contextcraft import ContextCraft, OutputFormat, __version__
from contextcraft.cli import app
from contextcraft.elider import TokenCounter

runner = CliRunner()


def test_sdk_end_to_end_markdown_xml_and_json(sample_repo: Path) -> None:
    """Verify `ContextCraft.compile()` produces valid Markdown, XML, and JSON with secrets scrubbed."""
    cc = ContextCraft(budget_tokens="2k", focus_query="JWT authentication")

    # 1. Markdown output
    md_res = cc.compile(sample_repo, output_format=OutputFormat.MARKDOWN)
    assert "# Repository Context:" in md_res.markdown
    assert "## Repository Directory Tree" in md_res.text_content
    assert "sk-proj-1234567890" not in md_res.content
    assert md_res.stats.secrets_redacted >= 1
    assert md_res.stats.compressed_tokens <= 2000

    # 2. XML output (must parse cleanly as well-formed XML)
    xml_res = cc.compile(sample_repo, output_format="xml")
    assert xml_res.stats.compressed_tokens <= 2000
    assert "sk-proj-1234567890" not in xml_res.content
    root_elem = ET.fromstring(xml_res.content)
    assert root_elem.tag == "repository_context"

    # 3. JSON output (must deserialize cleanly as valid JSON)
    json_res = cc.compile(sample_repo, output_format=OutputFormat.JSON)
    assert json_res.stats.compressed_tokens <= 2000
    payload = json.loads(json_res.content)
    assert payload["budget_tokens"] == 2000
    assert isinstance(payload["files"], list)


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


def test_cli_encoding_flag_selects_tokenizer_encoding(sample_repo: Path, tmp_path: Path) -> None:
    """Verify `--encoding` / `-enc` is advertised and forwarded to token accounting."""
    # 1. The flag must be discoverable from the CLI help output.
    help_res = runner.invoke(app, ["--help"])
    assert help_res.exit_code == 0
    assert "--encoding" in help_res.stdout
    assert "-enc" in help_res.stdout

    # 2. The selected encoding must reach the TokenCounter that enforces the budget.
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
