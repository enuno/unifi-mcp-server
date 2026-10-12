"""``python -m src`` runs the server entry point."""

import runpy
import sys
import types
from unittest.mock import MagicMock, patch


def test_module_execution_calls_main() -> None:
    # Stub src.main: importing the real one builds Settings from the environment.
    stub = types.ModuleType("src.main")
    stub.main = MagicMock()  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"src.main": stub}):
        runpy.run_module("src", run_name="__main__")

    stub.main.assert_called_once_with()
