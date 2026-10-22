from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contextcraft import CompilationConfig, ContextCraft, FidelityLevel
from contextcraft.ast import ParsedAst
from contextcraft.elider import Elider, TokenCounter
from contextcraft.formatter import ArtifactFormatter
from contextcraft.languages.javascript.language import JavaScriptLanguage
from contextcraft.models import FileAnalysis


def test_xml_handles_cdata_end_markers_and_xml_forbidden_characters(tmp_path: Path) -> None:
    # Keep Windows-invalid filename characters in metadata, not on disk.
    name = 'a&"]]>.js'
    source = b'const value = "]]> & \x01";'
    counter = TokenCounter()
    parsed = ParsedAst(source=source)
    file = FileAnalysis(
        rel_path=name,
        abs_path=str(tmp_path / "source.js"),
        language="javascript",
        size_bytes=len(source),
        parsed=parsed,
        tiers=Elider(counter).render(parsed, JavaScriptLanguage),
        selected_fidelity=FidelityLevel.FULL,
    )
    formatter = ArtifactFormatter(CompilationConfig(output_format="xml"), counter)
    result = formatter.format_result(
        root_path=tmp_path,
        files=[file],
        total_files_discovered=1,
        binary_files_skipped=0,
        ignored_files_skipped=0,
        execution_time_ms=0.0,
    )
    root = ET.fromstring(result.content)
    element = root.find("./files/file")

    assert element is not None
    assert element.attrib["path"] == name
    assert element.text == 'const value = "]]> & \\u0001";'


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_markdown_fences_cannot_be_closed_by_file_contents(tmp_path: Path, newline: str) -> None:
    source = f"``````{newline}source{newline}``````{newline}"
    (tmp_path / "example.unknown").write_bytes(source.encode("utf-8"))

    result = ContextCraft().compile(tmp_path)

    assert f"```````text\n{source}```````" in result.content


def test_minimal_json_is_valid_with_a_character_counter() -> None:
    class Counter:
        def count(self, text: str) -> int:
            return len(text)

    formatter = ArtifactFormatter(
        CompilationConfig(budget_tokens=1, output_format="json"), Counter()
    )
    result = formatter.format_result(
        root_path=".",
        files=[],
        total_files_discovered=0,
        binary_files_skipped=0,
        ignored_files_skipped=0,
        execution_time_ms=0.0,
    )

    assert result.stats.compressed_tokens == 1
    assert json.loads(result.content) == 0
