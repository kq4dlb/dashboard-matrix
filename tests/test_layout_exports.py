from app.layout_exports import _clean_folder, _slugify


def test_slugify():
    assert _slugify("KQ4DLB Home Dashboard") == "kq4dlb-home-dashboard"


def test_clean_folder():
    assert _clean_folder("layouts/My Layouts") == "layouts/my-layouts"


def test_clean_folder_removes_parent_segments():
    assert _clean_folder("../layouts") == "layouts/layouts"


def test_publish_document_validation_accepts_export():
    from app.layout_exports import _validated_publish_document

    document = {
        "schema_version": 1,
        "export_type": "dashboard-matrix-layout",
        "dashboards": [],
    }
    assert _validated_publish_document(document) is document


def test_publish_document_validation_rejects_other_json():
    import pytest
    from app.layout_exports import _validated_publish_document

    with pytest.raises(ValueError):
        _validated_publish_document({"schema_version": 1, "dashboards": []})
