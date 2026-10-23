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
