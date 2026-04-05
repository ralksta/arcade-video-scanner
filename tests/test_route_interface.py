"""
test_route_interface.py
-----------------------
Contract tests: Verify that every route module exports the expected
handle_get() and handle_post() dispatcher functions.

Why this exists:
    api_handler.py calls `module.handle_get(handler)` and
    `module.handle_post(handler)` on every route module. If a module
    is refactored without adding these adapters, the server silently
    errors on every request to that module's endpoints.

    This test catches that class of bug at CI time, not at runtime.
"""
import importlib
import pkgutil
import inspect

import pytest

# All route modules that api_handler.py dispatches through
ROUTE_MODULES = [
    "arcade_scanner.server.routes.queue",
    "arcade_scanner.server.routes.settings",
    "arcade_scanner.server.routes.duplicates",
    "arcade_scanner.server.routes.tags",
    "arcade_scanner.server.routes.files",
]


@pytest.mark.parametrize("module_path", ROUTE_MODULES)
def test_route_module_has_handle_get(module_path):
    """Every route module must expose a handle_get(handler) function."""
    mod = importlib.import_module(module_path)
    assert hasattr(mod, "handle_get"), (
        f"{module_path} is missing handle_get() — "
        "api_handler.py will crash on every GET request to this module's endpoints."
    )
    assert callable(mod.handle_get), f"{module_path}.handle_get must be callable"
    sig = inspect.signature(mod.handle_get)
    params = list(sig.parameters)
    assert len(params) >= 1, (
        f"{module_path}.handle_get must accept at least one parameter (handler)"
    )


@pytest.mark.parametrize("module_path", ROUTE_MODULES)
def test_route_module_has_handle_post(module_path):
    """Every route module must expose a handle_post(handler) function."""
    mod = importlib.import_module(module_path)
    assert hasattr(mod, "handle_post"), (
        f"{module_path} is missing handle_post() — "
        "api_handler.py will crash on every POST request to this module's endpoints."
    )
    assert callable(mod.handle_post), f"{module_path}.handle_post must be callable"
    sig = inspect.signature(mod.handle_post)
    params = list(sig.parameters)
    assert len(params) >= 1, (
        f"{module_path}.handle_post must accept at least one parameter (handler)"
    )


@pytest.mark.parametrize("module_path", ROUTE_MODULES)
def test_route_handle_get_returns_bool(module_path):
    """
    handle_get/handle_post must return bool so api_handler.py knows
    whether the route was handled. Verify the annotation (if present).
    """
    mod = importlib.import_module(module_path)
    for fn_name in ("handle_get", "handle_post"):
        fn = getattr(mod, fn_name)
        hints = fn.__annotations__
        if "return" in hints:
            ret = hints["return"]
            # Annotation can be the type or the string "bool" (from __future__ annotations)
            assert ret in (bool, "bool"), (
                f"{module_path}.{fn_name} return annotation must be bool, "
                f"got {ret!r}"
            )
