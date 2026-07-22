from app.updates import _version


def test_release_versions_compare_prerelease_numbers():
    assert _version("v0.1.0-beta.2") > _version("0.1.0-beta")
    assert _version("0.1.0") > _version("0.1.0-beta.9")
    assert _version("0.2.0-beta") > _version("0.1.9")
