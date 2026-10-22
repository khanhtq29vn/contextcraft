from __future__ import annotations

from tree_sitter_language_pack import get_parser

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import PythonLanguage


def test_python_decorators_and_docstrings_survive_skeleton_elision() -> None:
    source = b'''@decorate
class Service:
    """Class documentation."""
    @staticmethod
    def run(value: int) -> int:
        """Method documentation."""
        return transform(value)
'''
    parsed = parse(source, PythonLanguage)
    symbols = {symbol.qualified_name: symbol for symbol in parsed.symbols}
    skeleton = PythonLanguage.skeleton_builder(PythonLanguage.spec).build(parsed)

    assert set(symbols) == {"Service", "Service.run"}
    assert "@decorate" in skeleton
    assert "@staticmethod" in skeleton
    assert "Class documentation." in skeleton
    assert "Method documentation." in skeleton
    assert "transform(value)" not in skeleton
    assert parsed.text(symbols["Service.run"].signature_range).startswith("@staticmethod")
    assert not get_parser("python").parse(skeleton.encode()).root_node.has_error
