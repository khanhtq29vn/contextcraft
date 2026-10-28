# Use the Python SDK

Add ContextCraft to your application's environment:

```bash
uv add contextcraft-ai
```

The SDK works without the `[cli]` extra. Once installed, create a compiler
with a `Config` and pass the repository directory to `compile()`:

```python
from pathlib import Path

from contextcraft import ContextCraft
from contextcraft.config import Config, OutputFormat

config = Config(
    budget_tokens=8000,
    focus_query="authentication",
    output_format=OutputFormat.JSON,
)
artifact = ContextCraft(config).compile(".")
Path("context.json").write_text(artifact.content, encoding="utf-8")
print(artifact.tokens, artifact.token_counts_estimated)
```

The compiler returns an `Artifact` and leaves writing it to your application.
If you save the output inside the repository, exclude that path before
compiling again so the artifact does not become input. The SDK cannot do this
automatically because, unlike the CLI, it has no output-path option.

## Change settings between calls

Because the compiler shares the supplied config rather than copying it, you
can change settings between calls by updating the same instance:

```python
from contextcraft import ContextCraft
from contextcraft.config import Config, OutputFormat

config = Config(budget_tokens=8000)
compiler = ContextCraft(config)
small = compiler.compile(".")

config.budget_tokens = 16000
config.output_format = OutputFormat.XML
large = compiler.compile(".")
```

Each call reads and analyzes the repository again rather than reusing a cached
snapshot, and there is no separate `analyze()` method. Unlike the CLI's
single-file mode, `compile(file_path)` scans the parent directory instead of
producing outlines for that file alone.

## Require exact token counts

```python
from contextcraft import ContextCraft
from contextcraft.config import Config

config = Config(budget_tokens=8000, allow_token_estimates=False)
artifact = ContextCraft(config).compile(".")
assert not artifact.token_counts_estimated
```

With estimates disabled, tokenizer loading or encoding failures propagate to
your application instead of producing approximate counts. Loading an encoding
may download its data, while an invalid encoding name always raises
`ValueError`, regardless of the estimate policy.

## Inspect intermediate results

To retain the index, source metadata, graph, scores, or tiers, run the stages
directly as shown in the [pipeline-stage
reference](../reference/api/stages.md). Keep records from the same analysis
together, since their file, module, and import IDs cannot be mixed across
analyses.

Configure languages on `ContextCraft` or `Indexer` before indexing so that
detected implementations are recorded in `index.languages`. Later stages reuse
that mapping rather than accepting separate language lists.

See [Configuration](../reference/configuration.md) for defaults and input
validation, and [Compiler](../reference/api/compiler.md) for errors and the
return contract.
