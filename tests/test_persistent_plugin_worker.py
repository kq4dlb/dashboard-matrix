from __future__ import annotations

import json
from pathlib import Path

import app.plugin_manager as plugin_manager


def _write_test_plugin(root: Path, *, persistent: bool = True) -> None:
    plugin_root = root / "counter"
    plugin_root.mkdir(parents=True)
    (plugin_root / "manifest.json").write_text(
        json.dumps(
            {
                "id": "counter",
                "name": "Counter",
                "version": "1.0.0",
                "persistent_worker": persistent,
                "widgets": [
                    {
                        "id": "counter",
                        "name": "Counter",
                        "module": "plugin.py",
                    }
                ],
                "permissions": [],
                "secrets": [],
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin.py").write_text(
        "count = 0\n"
        "def render(widget_id, settings, station):\n"
        "    global count\n"
        "    count += 1\n"
        "    return {'format': 'metrics', 'count': count}\n",
        encoding="utf-8",
    )


def test_plugin_worker_preserves_module_state(monkeypatch, tmp_path):
    _write_test_plugin(tmp_path)
    monkeypatch.setattr(plugin_manager, "PLUGIN_DIRS", [tmp_path])
    plugin_manager.shutdown_plugin_workers()

    first = plugin_manager.run_plugin_widget("counter", "counter", {}, {})
    second = plugin_manager.run_plugin_widget("counter", "counter", {}, {})

    assert first["count"] == 1
    assert second["count"] == 2
    plugin_manager.shutdown_plugin_workers()


def test_plugin_worker_restarts_when_source_changes(monkeypatch, tmp_path):
    _write_test_plugin(tmp_path)
    monkeypatch.setattr(plugin_manager, "PLUGIN_DIRS", [tmp_path])
    plugin_manager.shutdown_plugin_workers()

    first = plugin_manager.run_plugin_widget("counter", "counter", {}, {})
    plugin_file = tmp_path / "counter" / "plugin.py"
    original = plugin_file.read_text(encoding="utf-8")
    plugin_file.write_text(original + "\n# source change\n", encoding="utf-8")

    second = plugin_manager.run_plugin_widget("counter", "counter", {}, {})

    assert first["count"] == 1
    assert second["count"] == 1
    plugin_manager.shutdown_plugin_workers()


def test_default_worker_remains_one_shot(monkeypatch, tmp_path):
    _write_test_plugin(tmp_path, persistent=False)
    monkeypatch.setattr(plugin_manager, "PLUGIN_DIRS", [tmp_path])
    plugin_manager.shutdown_plugin_workers()

    first = plugin_manager.run_plugin_widget("counter", "counter", {}, {})
    second = plugin_manager.run_plugin_widget("counter", "counter", {}, {})

    assert first["count"] == 1
    assert second["count"] == 1
