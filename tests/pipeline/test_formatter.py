from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from contextcraft import CompilationConfig, ContextCraft
from contextcraft.formatter import ArtifactFormatter


def test_xml_handles_cdata_end_markers_and_xml_forbidden_characters(tmp_path: Path) -> None:
    name = 'a&"]]>.js'
    (tmp_path / name).write_text('const value = "]]> & \x01";')

    result = ContextCraft(output_format="xml").compile(tmp_path)
    root = ET.fromstring(result.content)
    element = root.find("./files/file")

    assert element is not None
    assert element.attrib["path"] == name
    assert element.text == 'const value = "]]> & \\u0001";'


def test_markdown_fences_cannot_be_closed_by_file_contents(tmp_path: Path) -> None:
    (tmp_path / "example.unknown").write_text("``````\nsource\n``````\n")

    result = ContextCraft().compile(tmp_path)

    assert "```````text\n``````\nsource\n``````\n```````" in result.content


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
