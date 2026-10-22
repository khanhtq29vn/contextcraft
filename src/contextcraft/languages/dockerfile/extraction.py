from __future__ import annotations

from typing import ClassVar

from tree_sitter import Node

from contextcraft.ast import ByteRange
from contextcraft.languages.rules.generic import GenericExtractor
from contextcraft.languages.structural import StructuralExtractor


class DockerfileRules(GenericExtractor):
    ALLOW_SYNTAX_ERRORS: ClassVar[bool] = False
    NODE_TYPES: ClassVar[dict[str, str]] = {
        "from_instruction": "instruction",
        "run_instruction": "instruction",
        "cmd_instruction": "instruction",
        "entrypoint_instruction": "instruction",
        "copy_instruction": "instruction",
        "add_instruction": "instruction",
        "env_instruction": "instruction",
        "arg_instruction": "instruction",
        "workdir_instruction": "instruction",
        "expose_instruction": "instruction",
        "user_instruction": "instruction",
        "volume_instruction": "instruction",
        "label_instruction": "instruction",
        "shell_instruction": "instruction",
        "healthcheck_instruction": "instruction",
        "stopsignal_instruction": "instruction",
        "onbuild_instruction": "instruction",
    }
    IMPORT_NODE_TYPES: ClassVar[frozenset[str]] = frozenset([])

    def is_doc_comment(self, node: Node, source: bytes) -> bool:
        return node.type in {"comment", "line_comment", "block_comment", "multiline_comment"}

    def name_node(self, node: Node) -> Node | None:
        return node.children[0] if node.children else None

    def symbol_name(self, node: Node, source: bytes) -> str | None:
        return source[node.start_byte : node.end_byte].decode("utf-8").splitlines()[0]

    def body_node(self, node: Node) -> Node | None:
        if node.type == "run_instruction":
            return next(
                (child for child in node.named_children if child.type == "shell_command"), None
            )
        return None

    def elidable_body_range(
        self, node: Node, source: bytes, doc_end_byte: int | None
    ) -> ByteRange | None:
        body = self.body_node(node)
        return ByteRange(body.start_byte, node.end_byte) if body is not None else None

    def is_reference(self, node: Node) -> bool:
        return False


class DockerfileExtractor(StructuralExtractor):
    rules = DockerfileRules
