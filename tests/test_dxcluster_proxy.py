import json

from app.map_adapter import _rewrite_root_relative


def test_rewrites_root_relative_asset_urls():
    source = '<script src="/map/live.js"></script>'
    result = _rewrite_root_relative(source)
    assert '/maps/dxcluster/upstream/map/live.js' in result


def test_does_not_rewrite_protocol_relative_urls():
    source = '<script src="//cdn.example.test/live.js"></script>'
    result = _rewrite_root_relative(source)
    assert result == source


def test_rewrites_root_relative_fetch():
    source = 'fetch("/map/data.php")'
    result = _rewrite_root_relative(source)
    assert (
        'fetch("/maps/dxcluster/upstream/map/data.php")'
        in result
    )
