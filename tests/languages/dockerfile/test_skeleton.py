from __future__ import annotations

from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import default_registry


def test_dockerfile_heredoc_elision_keeps_the_instruction_valid() -> None:
    language = default_registry().get("dockerfile")
    assert language is not None
    source = b"FROM ubuntu\nRUN <<EOF\necho hello\nEOF\nCMD echo done\n"
    parsed = parse(source, language)
    assert not parsed.has_errors
    skeleton = language.skeleton_builder(language.spec).build(parsed)
    assert skeleton == "FROM ubuntu\nRUN true\nCMD echo done\n"
    assert not get_parser("dockerfile").parse(skeleton.encode()).root_node.has_error
