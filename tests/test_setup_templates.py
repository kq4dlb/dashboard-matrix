import pytest

from app.database import connection
from app.starter_templates import STARTER_TEMPLATES, install_template


@pytest.mark.parametrize("template_id", ["blank", "amateur-radio", "home-lab"])
def test_starter_template_installs(template_id, fresh_client):
    with connection() as conn:
        dashboard_ids = install_template(conn, template_id, replace_existing=True)
        count = conn.execute("SELECT COUNT(*) FROM dashboards").fetchone()[0]
    assert len(dashboard_ids) == len(STARTER_TEMPLATES[template_id]["dashboards"])
    assert count == len(STARTER_TEMPLATES[template_id]["dashboards"])
