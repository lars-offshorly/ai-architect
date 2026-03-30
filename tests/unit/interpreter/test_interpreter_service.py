from __future__ import annotations

import inspect

from agents.interpreter.service import InterpreterService


def test_interpret_returns_extraction_result_type() -> None:
    """InterpreterService.interpret() must return ExtractionResult."""

    sig = inspect.signature(InterpreterService.interpret)
    # Return annotation should reference ExtractionResult
    hints = sig.return_annotation
    assert "ExtractionResult" in str(hints)
