from app.map_adapter import PRESETS, profile_payload


def test_continental_us_preset_exists():
    profile = PRESETS["continental-us"]
    assert profile["center_lat"] == 39.8283
    assert profile["center_lon"] == -98.5795
    assert profile["bounds"][0][0] < profile["bounds"][1][0]


def test_regional_presets_have_names_and_zoom():
    for key, value in PRESETS.items():
        assert value["name"]
        assert 1 <= value["zoom"] <= 18
