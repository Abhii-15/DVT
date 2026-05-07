"""CAN package helpers.

This package is imported as ``src.can`` by the app. In some execution modes
(``src`` added directly to ``sys.path``), Python may also import this package as
top-level ``can``, which conflicts with the third-party ``python-can`` package.
When imported as top-level ``can``, proxy to the real ``python-can`` module.
"""

import importlib
from pathlib import Path
import sys


def _load_real_python_can():
    # Exclude this project's "src" path so import resolves the external package.
    local_src = str(Path(__file__).resolve().parents[1])
    original_path = list(sys.path)
    existing = sys.modules.get('can')
    try:
        sys.path = [p for p in original_path if str(Path(p).resolve()) != local_src]
        if 'can' in sys.modules:
            del sys.modules['can']
        module = importlib.import_module('can')
        return module
    finally:
        sys.path = original_path
        if existing is not None and sys.modules.get('can') is None:
            sys.modules['can'] = existing


if __name__ == 'can':
    _real_can = _load_real_python_can()
    globals().update(_real_can.__dict__)
else:
    from .can_manager import CANInterface, CANManager
    from .channel_map import ChannelEntry, ChannelMap, ChannelMapError, ChannelMapModel, SUPPORTED_BUSTYPES
    from .channel_manager import Channel, ChannelManager
    from .database_manager import Database, DatabaseManager
    from .router import Router

    __all__ = [
        'CANManager',
        'CANInterface',
        'ChannelEntry',
        'ChannelMap',
        'ChannelMapError',
        'ChannelMapModel',
        'SUPPORTED_BUSTYPES',
        'Channel',
        'ChannelManager',
        'Database',
        'DatabaseManager',
        'Router',
    ]
