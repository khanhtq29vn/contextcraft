from __future__ import annotations

from contextcraft.languages.structural import BlockSignaturesBuilder


class SignaturesBuilder(BlockSignaturesBuilder):
    opening = ""
    closing = "end"
    function_suffix = "\nend"

    def _render_function(self, signature: str) -> str:
        if signature.endswith("="):
            return signature + " nil"
        return super()._render_function(signature)
