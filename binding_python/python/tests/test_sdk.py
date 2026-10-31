from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from contextcraft import (
    Config,
    ContextCraft,
    FidelityLevel,
    OutputFormat,
    TokenCounter,
    TokenizerEncoding,
)


class SDKTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "main.py").write_text(
            "from helper import ready\nprint(ready())\n", encoding="utf-8"
        )
        (self.root / "helper.py").write_text(
            "def ready():\n    return True\n", encoding="utf-8"
        )

    def test_run_accepts_pathlike_and_string_roots(self) -> None:
        for root in (self.root, str(self.root)):
            with self.subTest(root=root):
                analysis = ContextCraft().run(root)
                self.assertEqual(analysis.index.root, self.root.resolve())
                self.assertEqual(len(analysis.index.files), 2)
                self.assertGreater(analysis.artifact.tokens, 0)

    def test_config_is_retained_and_mutations_apply_to_the_next_run(self) -> None:
        config = Config(budget_tokens=2_000)
        pipeline = ContextCraft(config)
        self.assertIs(pipeline.config, config)
        first = pipeline.run(self.root)
        original = first.artifact.content
        config.budget_tokens = 64
        config.output_format = OutputFormat.JSON
        config.focus_query = "ready"
        second = pipeline.run(self.root)

        self.assertLessEqual(second.artifact.tokens, 64)
        self.assertIsInstance(json.loads(second.artifact.content), dict)
        self.assertEqual(first.artifact.content, original)
        self.assertTrue(original.startswith("# Repository context"))

    def test_collection_fields_are_copies_until_reassigned(self) -> None:
        config = Config(focus_files=["main.py"], exclude_patterns=["ignored/**"])
        focus = config.focus_files
        focus.append("helper.py")
        exclusions = config.exclude_patterns
        exclusions.clear()

        self.assertEqual(config.focus_files, ["main.py"])
        self.assertEqual(config.exclude_patterns, ["ignored/**"])
        config.focus_files = focus
        self.assertEqual(config.focus_files, ["main.py", "helper.py"])
        self.assertEqual(
            Config(focus_files=None, exclude_patterns=None).focus_files, []
        )

    def test_invalid_configurations_raise_python_exceptions(self) -> None:
        for field in ("budget_tokens", "max_file_size_bytes"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    Config(**{field: 0})
                with self.assertRaises(OverflowError):
                    Config(**{field: -1})
                config = Config()
                setattr(config, field, 0)
                with self.assertRaises(ValueError):
                    ContextCraft(config).run(self.root)

        with self.assertRaises(TypeError):
            Config(unknown_setting=True)
        with self.assertRaises(TypeError):
            Config(budget_tokens="invalid")

    def test_filesystem_manifest_and_budget_errors_map_to_python(self) -> None:
        with self.assertRaises(OSError):
            ContextCraft().run(self.root / "missing")
        with self.assertRaises(NotADirectoryError):
            ContextCraft().run(self.root / "main.py")
        with self.assertRaisesRegex(ValueError, "token budget"):
            ContextCraft(Config(budget_tokens=1)).run(self.root)

        (self.root / "Cargo.toml").write_text("[package\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "manifest"):
            ContextCraft().run(self.root)

    def test_snapshot_file_ids_connect_sources_scores_tiers_and_edges(self) -> None:
        analysis = ContextCraft().run(self.root)
        ids = set(analysis.index.files)

        self.assertEqual(set(analysis.repository.sources), ids)
        self.assertEqual(set(analysis.scores), ids)
        self.assertEqual(set(analysis.tiers.files), ids)
        self.assertEqual(set(analysis.artifact.selected_tiers), ids)
        self.assertAlmostEqual(sum(analysis.scores.values()), 1.0)
        self.assertTrue(
            all(not file.path.is_absolute() for file in analysis.index.files.values())
        )
        paths = {
            file_id: file.path.as_posix()
            for file_id, file in analysis.index.files.items()
        }
        edges = {
            (paths[source], paths[target])
            for source, target in analysis.graph.dependencies
        }
        self.assertEqual(edges, {("main.py", "helper.py")})

        for file_id, source in analysis.repository.sources.items():
            self.assertIsInstance(source.bytes, bytes)
            self.assertEqual(source.bytes, (self.root / paths[file_id]).read_bytes())

    def test_all_tokenizer_encodings_count_ordinary_special_markers(self) -> None:
        encodings = (
            TokenizerEncoding.GPT2,
            TokenizerEncoding.R50K_BASE,
            TokenizerEncoding.P50K_BASE,
            TokenizerEncoding.P50K_EDIT,
            TokenizerEncoding.CL100K_BASE,
            TokenizerEncoding.O200K_BASE,
            TokenizerEncoding.O200K_HARMONY,
        )
        for encoding in encodings:
            with self.subTest(encoding=encoding):
                counter = TokenCounter(encoding, allow_estimates=False)
                self.assertEqual(counter.count(""), 0)
                self.assertEqual(counter.count("hello world"), 2)
                self.assertGreater(counter.count("<|endoftext|>"), 1)
                self.assertFalse(counter.used_estimates())

    def test_full_source_counts_match_direct_counts_in_both_execution_modes(
        self,
    ) -> None:
        (self.root / "binary.dat").write_bytes(b"\x00\xff")
        analysis = ContextCraft().run(self.root)
        counter = TokenCounter()
        expected = {
            file_id: counter.count(tiers.levels[FidelityLevel.FULL].content)
            for file_id, tiers in analysis.tiers.files.items()
            if FidelityLevel.FULL in tiers.levels
        }

        self.assertEqual(counter.count_full_sources(analysis.tiers, False), expected)
        self.assertEqual(counter.count_full_sources(analysis.tiers, True), expected)
        self.assertEqual(
            counter.count(analysis.artifact.content), analysis.artifact.tokens
        )
        self.assertEqual(len(expected), 2)

    def test_sdk_import_does_not_load_optional_cli_dependencies(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, contextcraft; assert 'rich' not in sys.modules; assert 'cyclopts' not in sys.modules",
            ],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
