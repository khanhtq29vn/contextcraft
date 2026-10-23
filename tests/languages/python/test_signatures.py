from __future__ import annotations

import ast

import pytest

from contextcraft.ast.parser import parse
from contextcraft.languages.builtin import PythonLanguage


def test_python_signatures_keep_type_default_decorator_and_forward_reference_imports() -> None:
    source = b"""from __future__ import annotations
import json
from pathlib import Path as FilePath
from models import Model
from helpers import decorate, default_value
from unused import implementation_only

@decorate
def run(path: FilePath, model: "Model", value=default_value()):
    return implementation_only(json.dumps(value))
"""
    parsed = parse(source, PythonLanguage)
    builder = PythonLanguage.signatures_builder(PythonLanguage.spec)

    signatures = builder.build(parsed)

    ast.parse(signatures)
    assert "from __future__ import annotations" in signatures
    assert "from pathlib import Path as FilePath" in signatures
    assert "from models import Model" in signatures
    assert "from helpers import decorate, default_value" in signatures
    assert "import json" not in signatures
    assert "from unused" not in signatures
    assert len(parsed.imports) == 6
    assert parsed.source == source


@pytest.mark.parametrize(
    "source",
    [
        b"from api import Client\n",
        b"from api import Client as Client\ndef run(): return 1\n",
        b'from api import Client\n__all__ = ["Client"]\ndef run(): return 1\n',
        b"from api import *\ndef run(): return 1\n",
    ],
)
def test_python_signatures_preserve_reexports_and_star_imports(source: bytes) -> None:
    parsed = parse(source, PythonLanguage)
    signatures = PythonLanguage.signatures_builder(PythonLanguage.spec).build(parsed)

    assert source.splitlines()[0].decode() in signatures


def test_selected_python_methods_keep_parent_context_and_valid_empty_classes() -> None:
    source = b"""class Client:
    def first(self, value: int) -> int:
        return value
    def second(self):
        return 2
"""
    parsed = parse(source, PythonLanguage)
    builder = PythonLanguage.signatures_builder(PythonLanguage.spec)
    method = next(symbol for symbol in parsed.symbols if symbol.name == "first")
    signatures = builder.build_selected(parsed, [method])

    ast.parse(signatures)
    assert "class Client:" in signatures
    assert "def first(" in signatures
    assert "def second(" not in signatures
    assert len(parsed.symbols) == 3
    assert parsed.source == source
    ast.parse(builder.build_selected(parsed, [parsed.symbols[0]]))
