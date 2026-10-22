from __future__ import annotations

from collections.abc import Iterator
from enum import Enum

from tree_sitter import Node


class TraversalEvent(Enum):
    ENTER = "enter"
    LEAVE = "leave"


def traverse(root: Node) -> Iterator[tuple[TraversalEvent, Node]]:
    cursor = root.walk()

    while True:
        node = cursor.node
        assert node is not None
        yield TraversalEvent.ENTER, node
        if cursor.goto_first_child():
            continue

        while True:
            node = cursor.node
            assert node is not None
            yield TraversalEvent.LEAVE, node
            if cursor.goto_next_sibling():
                break
            if not cursor.goto_parent():
                return
