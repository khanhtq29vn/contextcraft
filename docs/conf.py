"""Sphinx configuration for the ContextCraft documentation."""

project = "ContextCraft"
author = "ContextCraft Contributors"

extensions = ["myst_parser", "sphinxcontrib.katex"]
myst_enable_extensions = ["dollarmath"]

html_theme = "furo"
html_title = "ContextCraft Documentation"
html_theme_options = {
    "source_repository": "https://github.com/contextcraft/contextcraft/",
    "source_branch": "main",
    "source_directory": "docs/",
}

exclude_patterns = ["_build"]
