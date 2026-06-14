import sys
from unittest.mock import patch


def test_python_m_entrypoint_passes_inputfile_to_engine(monkeypatch):
    """The module entrypoint should expose python -m assethold <input.yml>."""
    from assethold import __main__ as main_module

    monkeypatch.setattr(sys, "argv", ["python -m assethold", "input.yml"])

    with patch.object(main_module, "engine") as mock_engine:
        main_module.main()

    mock_engine.assert_called_once_with("input.yml")
