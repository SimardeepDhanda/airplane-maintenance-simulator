import importlib


def test_package_imports() -> None:
    module = importlib.import_module("aerofleet_opt")
    assert module.__doc__ is not None
