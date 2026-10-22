# CLI & Python SDK Reference

## Command-Line Interface (`contextcraft`)

```bash
contextcraft [PATH] [OPTIONS]
```

### Key Options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--budget`, `-b` | Strict token budget (`4k`, `16k`, `32k`, `128k`, or integer) | `32k` |
| `--encoding`, `-enc` | Tiktoken encoding name used for token accounting (e.g. `cl100k_base`, `o200k_base`) | `cl100k_base` |
| `--focus`, `-f` | Natural-language query or symbol keywords for Personalized PageRank | `None` |
| `--focus-file` | Relative file path or glob to boost in PageRank (repeatable) | `[]` |
| `--format`, `-m` | Target output format: `markdown`, `xml`, or `json` | `markdown` |
| `--output`, `-o` | Write compiled artifact to file path instead of `stdout` | `None` |
| `--copy`, `-c` | Copy compiled artifact directly to system clipboard | `False` |
| `--no-redact` | Disable automatic secret and API key scrubbing | `False` |

---

## Python SDK (`ContextCraft`)

```python
from contextcraft import ContextCraft, OutputFormat

cc = ContextCraft(
    budget_tokens="16k",
    focus_query="dependency graph pagerank",
    output_format=OutputFormat.XML,
)
result = cc.compile(".")
print(f"Compressed {result.stats.raw_tokens} -> {result.stats.compressed_tokens} tokens")
print(f"Compression ratio: {result.stats.compression_ratio}x")
```
