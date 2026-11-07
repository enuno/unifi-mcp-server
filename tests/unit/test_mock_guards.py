"""Guards against the async mock that hides a failure.

``async with`` asks the context manager's ``__aexit__`` whether the
exception raised inside the block should be suppressed. A mock set to a
bare ``AsyncMock()`` answers with a truthy mock, so the exception is
swallowed: a test that asserts a successful result passes even when the
code under test raised.

The mock has to say it does not suppress, with ``return_value=False``.
"""

import re
from pathlib import Path

_TESTS_ROOT = Path(__file__).resolve().parent

# A bare AsyncMock(), or one that says it suppresses.
_BARE_AEXIT = re.compile(r"__aexit__\s*=\s*AsyncMock\(\s*\)")
_SUPPRESSING_AEXIT = re.compile(r"__aexit__\s*=\s*AsyncMock\([^)]*return_value\s*=\s*True")


def _offenders(pattern: re.Pattern[str]) -> list[str]:
    found: list[str] = []
    for path in sorted(_TESTS_ROOT.rglob("test_*.py")):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.search(line):
                found.append(f"{path.relative_to(_TESTS_ROOT)}:{number}")
    return found


def test_no_test_suppresses_an_exception_through_a_mock():
    """A mock's __aexit__ must not answer "suppress it"."""
    offenders = _offenders(_BARE_AEXIT) + _offenders(_SUPPRESSING_AEXIT)
    assert not offenders, (
        "A bare AsyncMock() as __aexit__ returns a truthy value, which "
        "suppresses the exception raised inside the async with block and "
        "lets a failing test pass. Use AsyncMock(return_value=False): " + ", ".join(offenders)
    )
