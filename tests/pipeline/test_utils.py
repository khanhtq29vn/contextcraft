from importlib.metadata import PackageNotFoundError

import pytest

from contextcraft import utils


def test_get_version_uses_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def distribution_version(name: str) -> str:
        assert name == "contextcraft-ai"
        return "1.2.3"

    monkeypatch.setattr(utils, "version", distribution_version)

    assert utils.get_version() == "1.2.3"


def test_get_version_without_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def distribution_version(name: str) -> str:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(utils, "version", distribution_version)

    assert utils.get_version() == "0.0.0"


@pytest.fixture
def posix_patterns(monkeypatch: pytest.MonkeyPatch) -> None:
    # On Windows a backslash in a pin pattern is a separator, not a gitignore escape.
    monkeypatch.setattr(utils, "_WINDOWS", False)


@pytest.mark.usefixtures("posix_patterns")
@pytest.mark.parametrize(
    ("pattern", "rel_path", "expected"),
    [
        ("src/auth/jwt.py", "src/auth/jwt.py", True),
        ("./src/auth/jwt.py", "src/auth/jwt.py", True),
        ("/src/auth/jwt.py", "src/auth/jwt.py", True),
        ("jwt.py", "src/auth/jwt.py", True),
        ("*.py", "src/auth/jwt.py", True),
        ("src/**/*.py", "src/auth/jwt.py", True),
        ("src/auth", "src/auth/jwt.py", True),
        ("src/auth/", "src/auth/jwt.py", True),
        (".env", ".env", True),
        ("a.py", "data.py", False),
        (".env", "src/environment.py", False),
        ("src/auth", "src/authentication/jwt.py", False),
        ("Models.py", "app/models.py", False),
        ("", "app/models.py", False),
        # Same gitignore semantics as --include/--exclude.
        ("legacy.py", "pkg/legacy.py", True),
        ("/legacy.py", "pkg/legacy.py", False),
        ("./legacy.py", "pkg/legacy.py", False),
        ("./legacy.py", "legacy.py", True),
        ("src/**/*.py", "src/jwt.py", True),
        ("**/*.py", "main.py", True),
        ("src/*.py", "src/a/b.py", False),
        ("app/\\[id\\]/page.tsx", "app/[id]/page.tsx", True),
        ("\\!important.py", "app/!important.py", True),
        ("/", "app/models.py", False),
    ],
)
def test_matches_path_patterns(pattern: str, rel_path: str, expected: bool) -> None:
    assert utils.matches_path_patterns(rel_path, [pattern]) is expected


@pytest.mark.usefixtures("posix_patterns")
def test_matches_path_patterns_supports_negation() -> None:
    assert utils.matches_path_patterns("app/core.py", ["*.py", "!free.py"])
    assert not utils.matches_path_patterns("app/free.py", ["*.py", "!free.py"])
    assert not utils.matches_path_patterns("app/core.py", [])


@pytest.mark.usefixtures("posix_patterns")
def test_matches_path_patterns_anchors_negated_dot_slash_patterns() -> None:
    assert not utils.matches_path_patterns("legacy.py", ["*.py", "!./legacy.py"])
    assert utils.matches_path_patterns("pkg/legacy.py", ["*.py", "!./legacy.py"])


def test_matches_path_patterns_accepts_backslashes_only_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(utils, "_WINDOWS", False)
    assert not utils.matches_path_patterns("src/auth/jwt.py", ["src\\auth\\jwt.py"])
    monkeypatch.setattr(utils, "_WINDOWS", True)
    assert utils.matches_path_patterns("src/auth/jwt.py", ["src\\auth\\jwt.py"])


@pytest.mark.usefixtures("posix_patterns")
def test_pin_patterns_treat_whitespace_like_gitignore() -> None:
    assert utils._normalize_pattern("legacy.py  ") == "legacy.py"
    assert utils._normalize_pattern("notes\\ ") == "notes\\ "
    assert utils.matches_path_patterns("notes ", ["notes\\ "])
    assert not utils.matches_path_patterns("legacy.py", ["  legacy.py"])
