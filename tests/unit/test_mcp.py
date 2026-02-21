import pytest

fastmcp = pytest.importorskip("fastmcp", reason="fastmcp not installed")


def test_mcp_server_importable():
    import maestro_fetch.interfaces.mcp_server as mcp
    assert hasattr(mcp, "mcp")
    assert hasattr(mcp, "run")
