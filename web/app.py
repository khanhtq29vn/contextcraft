"""FastAPI Interactive Web Playground and Viral URL-Swap Server for ContextCraft.

Provides three core developer experiences:
1. Interactive Web UI (`GET /`): Allows developers to compress either a local repository
   path (e.g., `.`) or any public GitHub repository (`https://github.com/owner/repo`),
   tune the token budget (`2k` to `128k`), enter a `--focus` query, and inspect the
   Personalized PageRank & AST fidelity breakdown visually.
2. Programmatic JSON API (`POST /api/compile`): Stateless compilation endpoint returning
   the compressed artifact, telemetry stats, and per-file PageRank table.
3. The Viral URL-Swap Trick (`GET /{owner}/{repo}`): Inspired by `gitingest.com` and
   `gitignore.io`, changing `https://github.com/owner/repo` to
   `http://localhost:8000/owner/repo?budget=32k&focus=auth` automatically clones
   and compresses the repository in the browser.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from contextcraft import (
    CompilationResult,
    ContextCraft,
    ContextCraftError,
    OutputFormat,
    __version__,
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_GITHUB_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
_SLUG_RE = re.compile(r"(?!\.{1,2}$)[A-Za-z0-9_.-]+")
_LOCAL_REPOSITORY_ROOT = (
    Path(os.environ.get("CONTEXTCRAFT_WEB_ROOT", os.getcwd())).expanduser().resolve()
)

app = FastAPI(
    title="ContextCraft Web Playground",
    description="AST-Aware, Dependency-Graph-Ranked, Token-Budgeted Codebase Compressor for LLMs.",
    version=__version__,
)


class CompileRequestPayload(BaseModel):
    """JSON request schema for `POST /api/compile`."""

    source: str = Field(
        default=".",
        description="Repository path within the configured web root OR public GitHub repository URL (`https://github.com/owner/repo`).",
    )
    budget: str | int = Field(
        default="16k",
        description="Strict token budget (e.g., '4k', '16k', '32k', '64k', or integer tokens).",
    )
    focus_query: str | None = Field(
        default=None,
        description="Optional natural-language focus query or symbol keywords for Personalized PageRank.",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.MARKDOWN,
        description="Target output format: markdown, xml, or json.",
    )
    redact_secrets: bool = Field(
        default=True,
        description="Automatically scrub API keys and high-entropy secrets before emission.",
    )


class FileTelemetryItem(BaseModel):
    """Per-file telemetry row returned to the Web Playground UI."""

    rel_path: str
    language: str
    fidelity: str
    pagerank_pct: float
    selected_tokens: int
    raw_tokens: int
    symbols_count: int


class CompileResponsePayload(BaseModel):
    """JSON response schema returned by `POST /api/compile`."""

    source: str
    output_format: OutputFormat
    content: str
    stats: dict[str, Any]
    files: list[FileTelemetryItem]


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Return service health and version metadata."""
    return {"status": "ok", "service": "contextcraft", "version": __version__}


@app.get("/", response_class=HTMLResponse)
def index_page(
    request: Request,
    source: str = Query(default=".", description="Initial source path or GitHub URL."),
    budget: str = Query(default="16k", description="Initial token budget."),
    focus: str = Query(default="", description="Initial focus query."),
    fmt: str = Query(default="markdown", description="Initial output format."),
) -> HTMLResponse:
    """Render the interactive ContextCraft Web Playground."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "version": __version__,
            "initial_source": source,
            "initial_budget": budget,
            "initial_focus": focus,
            "initial_format": fmt if fmt in {"markdown", "xml", "json"} else "markdown",
            "auto_run": False,
        },
    )


def _resolve_local_repository(source: str) -> Path:
    if "\x00" in source:
        raise HTTPException(status_code=400, detail="Invalid repository path.")
    root = os.fspath(_LOCAL_REPOSITORY_ROOT)
    try:
        relative = os.path.relpath(os.path.join(root, os.path.expanduser(source)), root)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail="Repository path must be within the configured web root.",
        ) from exc

    # Rejoin to retain the configured root's casing on Windows.
    normalized = os.path.normpath(os.path.join(root, relative))
    if normalized == root:
        return _LOCAL_REPOSITORY_ROOT
    if not normalized.startswith(os.path.join(root, "")):
        raise HTTPException(
            status_code=403,
            detail="Repository path must be within the configured web root.",
        )
    try:
        local_path = Path(normalized).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid repository path.") from exc
    if not local_path.is_relative_to(_LOCAL_REPOSITORY_ROOT):
        raise HTTPException(
            status_code=403,
            detail="Repository path must be within the configured web root.",
        )
    return _LOCAL_REPOSITORY_ROOT / local_path.relative_to(_LOCAL_REPOSITORY_ROOT)


@app.post("/api/compile", response_model=CompileResponsePayload)
def api_compile(payload: CompileRequestPayload) -> CompileResponsePayload:
    """Compile either a local repository or a remote GitHub URL within budget."""
    source_str = payload.source.strip() or "."
    focus_clean = payload.focus_query.strip() if payload.focus_query else None

    try:
        compiler = ContextCraft(
            budget_tokens=payload.budget,
            focus_query=focus_clean,
            output_format=payload.output_format,
            redact_secrets=payload.redact_secrets,
        )

        gh_match = _GITHUB_URL_RE.match(source_str)
        if gh_match:
            owner = gh_match.group("owner")
            repo = gh_match.group("repo")
            result = _clone_and_compile_github_repo(compiler, owner=owner, repo=repo)
        else:
            result = compiler.compile(_resolve_local_repository(source_str))
    except ContextCraftError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except subprocess.SubprocessError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to clone remote GitHub repository: {exc}",
        ) from exc

    ranked_files = sorted(result.files, key=lambda f: (-f.pagerank_score, f.rel_path))
    file_rows = [
        FileTelemetryItem(
            rel_path=f.rel_path,
            language=f.language,
            fidelity=f.selected_fidelity.badge,
            pagerank_pct=round(f.pagerank_score * 100.0, 2),
            selected_tokens=f.selected_tokens,
            raw_tokens=f.raw_tokens,
            symbols_count=len(f.symbols),
        )
        for f in ranked_files
    ]

    return CompileResponsePayload(
        source=source_str,
        output_format=result.output_format,
        content=result.content,
        stats=result.stats.model_dump(),
        files=file_rows,
    )


@app.get("/{owner}/{repo}", response_class=HTMLResponse)
def github_url_swap_page(
    request: Request,
    owner: str,
    repo: str,
    budget: str = Query(default="32k"),
    focus: str = Query(default=""),
    fmt: str = Query(default="markdown"),
) -> HTMLResponse:
    """Viral URL-Swap endpoint: `<domain>/{owner}/{repo}?budget=32k&focus=auth`."""
    if not (_SLUG_RE.fullmatch(owner) and _SLUG_RE.fullmatch(repo)):
        raise HTTPException(status_code=400, detail="Invalid GitHub owner or repository name.")

    github_url = f"https://github.com/{owner}/{repo}"
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "version": __version__,
            "initial_source": github_url,
            "initial_budget": budget,
            "initial_focus": focus,
            "initial_format": fmt if fmt in {"markdown", "xml", "json"} else "markdown",
            "auto_run": True,
        },
    )


def _clone_and_compile_github_repo(
    compiler: ContextCraft,
    *,
    owner: str,
    repo: str,
) -> CompilationResult:
    """Perform a shallow `git clone --depth 1` into a temp directory and compile it."""
    if not (_SLUG_RE.fullmatch(owner) and _SLUG_RE.fullmatch(repo)):
        raise ContextCraftError(f"Invalid GitHub repository slug: {owner}/{repo}")

    git_bin = shutil.which("git")
    if git_bin is None:
        raise ContextCraftError("Git executable is not installed on the server.")

    clone_url = f"https://github.com/{owner}/{repo}.git"
    with tempfile.TemporaryDirectory(prefix="contextcraft_gh_") as tmp_root:
        target_dir = Path(tmp_root) / "repository"
        subprocess.run(
            [git_bin, "clone", "--depth", "1", "--single-branch", clone_url, str(target_dir)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=45,
        )
        return compiler.compile(target_dir)
