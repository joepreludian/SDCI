"""Tests for the throttled upload progress reporter."""

import logging

import pytest

from sdci.server_runner import UploadProgressReporter, format_bytes

LOGGER_NAME = "sdci.server_runner"
MIB = 1024 * 1024


class FakeClock:
    """Deterministic monotonic clock so throttling is testable without sleeping."""

    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _reporter(clock, total_bytes=120 * MIB, label="10.0.0.4"):
    return UploadProgressReporter(
        label, total_bytes=total_bytes, interval_seconds=2.0, clock=clock
    )


@pytest.mark.parametrize(
    "num_bytes, expected",
    [
        (512, "512.0 B"),
        (1024, "1.0 KiB"),
        (16 * MIB, "16.0 MiB"),
        (2 * 1024 * MIB, "2.0 GiB"),
    ],
)
def test_format_bytes_renders_binary_units(num_bytes, expected):
    assert format_bytes(num_bytes) == expected


def test_advance_accumulates_received_bytes():
    reporter = _reporter(FakeClock())

    reporter.advance(4 * MIB)
    reporter.advance(6 * MIB)

    assert reporter.bytes_received == 10 * MIB


def test_advance_stays_quiet_before_the_interval_elapses(caplog):
    clock = FakeClock()
    reporter = _reporter(clock)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        clock.advance(1.9)
        reporter.advance(16 * MIB)

    assert caplog.records == []


def test_advance_logs_progress_once_the_interval_elapses(caplog):
    clock = FakeClock()
    reporter = _reporter(clock)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        clock.advance(2.0)
        reporter.advance(16 * MIB)

    assert caplog.messages == [
        "UPLOAD PROGRESS - 10.0.0.4 - 16.0 MiB / 120.0 MiB (13%) - 8.0 MiB/s"
    ]


def test_advance_logs_again_only_after_another_interval(caplog):
    clock = FakeClock()
    reporter = _reporter(clock)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        clock.advance(2.0)
        reporter.advance(16 * MIB)
        clock.advance(1.0)
        reporter.advance(8 * MIB)
        clock.advance(1.0)
        reporter.advance(8 * MIB)

    assert len(caplog.messages) == 2
    assert caplog.messages[1].startswith("UPLOAD PROGRESS - 10.0.0.4 - 32.0 MiB")


def test_progress_omits_total_and_percentage_when_length_is_unknown(caplog):
    clock = FakeClock()
    reporter = _reporter(clock, total_bytes=None)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        clock.advance(2.0)
        reporter.advance(16 * MIB)

    assert caplog.messages == ["UPLOAD PROGRESS - 10.0.0.4 - 16.0 MiB - 8.0 MiB/s"]


def test_summary_omits_rate_when_no_time_has_elapsed():
    reporter = _reporter(FakeClock())

    reporter.advance(16 * MIB)

    assert (
        reporter.summary() == "UPLOAD PROGRESS - 10.0.0.4 - 16.0 MiB / 120.0 MiB (13%)"
    )


def test_finish_logs_the_received_total_and_elapsed_time(caplog):
    clock = FakeClock()
    reporter = _reporter(clock)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        reporter.advance(32 * MIB)
        clock.advance(4.0)
        reporter.finish()

    assert caplog.messages == [
        "UPLOAD RECEIVED - 10.0.0.4 - 32.0 MiB in 4.0s - 8.0 MiB/s"
    ]
