from app.plugin_manager import public_plugin


def test_plugin_runtime_readiness_requires_approvals(monkeypatch):
    plugin = {
        "id": "sample",
        "name": "Sample",
        "permissions": ["network", "secrets"],
        "secrets": [{"name": "api_key", "required": True, "description": ""}],
        "widgets": [],
    }
    result = public_plugin(
        plugin,
        approvals=["network"],
        secret_refs={"api_key": "MATRIX_SAMPLE_KEY"},
    )
    assert result["permission_ready"] is False
    assert result["secret_status"]["api_key"] is False
