import pytest
import respx

from app.clients.power import POWER_URL
from tests.fakes import power_responder

BODY = {"region": {"type": "point", "lat": 28.61, "lon": 77.21, "label": "Delhi"}, "start_year": 1990, "end_year": 2020}


@pytest.fixture
def analysis_id(client):
    with respx.mock:
        respx.get(POWER_URL).mock(side_effect=power_responder())
        return client.post("/api/analyze", json=BODY).json()["id"]


def test_csv_export_has_yearly_and_event_sections(client, analysis_id):
    response = client.get(f"/api/analyses/{analysis_id}/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.splitlines()
    assert lines[0] == "# Heatwave analysis: Delhi, 1990-2020"
    assert "year,HWN,HWF,HWD,HWM,HWA,low_quality" in lines
    assert "start,end,days,peak_tmax,mean_exceedance" in lines
    assert sum(1 for line in lines if line[:4].isdigit() and line[4] == ",") == 31


def test_pdf_report_is_a_pdf(client, analysis_id):
    response = client.get(f"/api/analyses/{analysis_id}/report.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_export_of_unknown_analysis_is_404(client):
    assert client.get("/api/analyses/" + "a" * 64 + "/export.csv").status_code == 404
