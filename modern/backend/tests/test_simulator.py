from __future__ import annotations

from app.simulator import DEFAULT_LINES, load_lines


def test_simulator_has_safe_default_fixture() -> None:
    assert DEFAULT_LINES
    assert any("DISARMED" in line for line in DEFAULT_LINES)
    assert all(not line.endswith("\n") for line in DEFAULT_LINES)


def test_simulator_loads_fixture(tmp_path) -> None:
    fixture = tmp_path / "capture.txt"
    fixture.write_text("one\n\n two \n")
    assert load_lines(fixture) == ["one", " two "]
