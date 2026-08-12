"""Tests for settings parsing (env vars arrive as strings and must become ints)."""

import importlib

import pytest

import sdci.settings as settings_module
from sdci.exceptions import SDCIFatalException

TIMEOUT_ENV_VARS = ("TASK_RUN_TIMEOUT", "CLIENT_REQUEST_TIMEOUT", "UPLOAD_TIMEOUT")


@pytest.fixture
def reloaded_settings(monkeypatch):
    """Re-import the settings module so env vars are read again.

    Restores the pristine module afterwards so other tests are unaffected.
    """
    yield lambda: importlib.reload(settings_module)

    for env_var in TIMEOUT_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    importlib.reload(settings_module)


def test_env_int_returns_default_when_var_is_unset(monkeypatch):
    monkeypatch.delenv("SDCI_SAMPLE_TIMEOUT", raising=False)

    assert settings_module.env_int("SDCI_SAMPLE_TIMEOUT", 120) == 120


def test_env_int_parses_string_value_into_int(monkeypatch):
    monkeypatch.setenv("SDCI_SAMPLE_TIMEOUT", "300")

    value = settings_module.env_int("SDCI_SAMPLE_TIMEOUT", 120)

    assert value == 300
    assert isinstance(value, int)


def test_env_int_raises_on_non_numeric_value(monkeypatch):
    monkeypatch.setenv("SDCI_SAMPLE_TIMEOUT", "abc")

    with pytest.raises(SDCIFatalException):
        settings_module.env_int("SDCI_SAMPLE_TIMEOUT", 120)


@pytest.mark.parametrize(
    "env_var, attribute",
    [
        ("TASK_RUN_TIMEOUT", "TASK_RUN_TIMEOUT_SECONDS"),
        ("CLIENT_REQUEST_TIMEOUT", "CLIENT_REQUEST_TIMEOUT_SECONDS"),
        ("UPLOAD_TIMEOUT", "UPLOAD_TIMEOUT_SECONDS"),
    ],
)
def test_timeout_env_var_is_exposed_as_int(
    monkeypatch, reloaded_settings, env_var, attribute
):
    monkeypatch.setenv(env_var, "300")

    reloaded = reloaded_settings()

    assert getattr(reloaded, attribute) == 300
    assert getattr(reloaded.Settings, attribute) == 300


@pytest.mark.parametrize(
    "env_var, attribute, expected_default",
    [
        ("TASK_RUN_TIMEOUT", "TASK_RUN_TIMEOUT_SECONDS", 600),
        ("CLIENT_REQUEST_TIMEOUT", "CLIENT_REQUEST_TIMEOUT_SECONDS", 1800),
        ("UPLOAD_TIMEOUT", "UPLOAD_TIMEOUT_SECONDS", 1800),
    ],
)
def test_timeout_default_applies_when_env_var_is_unset(
    monkeypatch, reloaded_settings, env_var, attribute, expected_default
):
    """Tasks default to 10 minutes, uploads to 30 minutes on both sides."""
    monkeypatch.delenv(env_var, raising=False)

    reloaded = reloaded_settings()

    assert getattr(reloaded, attribute) == expected_default
    assert getattr(reloaded.Settings, attribute) == expected_default
