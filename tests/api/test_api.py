import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "up"
    assert "database" in json_data
    assert json_data["database"]["status"] == "healthy"
    assert json_data["database"]["metrics"]["companies"] > 0

def test_list_companies():
    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Check fields of the first company
    first = data[0]
    assert "id" in first
    assert "company_name" in first
    assert "broad_sector" in first

def test_list_companies_search():
    response = client.get("/api/v1/companies?q=HDFCBANK")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "HDFCBANK"

def test_list_companies_filter_sector():
    response = client.get("/api/v1/companies?sector=Financials")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for comp in data:
        assert comp["broad_sector"] == "Financials"

def test_get_company_profile():
    response = client.get("/api/v1/companies/HDFCBANK")
    assert response.status_code == 200
    profile = response.json()
    assert profile["id"] == "HDFCBANK"
    assert "company_name" in profile
    assert "broad_sector" in profile
    assert "cluster_name" in profile
    assert "pros" in profile
    assert "cons" in profile

def test_get_company_profile_not_found():
    response = client.get("/api/v1/companies/INVALIDTICKER")
    assert response.status_code == 404

def test_get_company_statements():
    # Test P&L
    response = client.get("/api/v1/companies/HDFCBANK/pl")
    assert response.status_code == 200
    pl = response.json()
    assert len(pl) > 0
    assert "sales" in pl[0]
    
    # Test BS
    response = client.get("/api/v1/companies/HDFCBANK/bs")
    assert response.status_code == 200
    bs = response.json()
    assert len(bs) > 0
    assert "equity_capital" in bs[0]
    
    # Test Cash Flow
    response = client.get("/api/v1/companies/HDFCBANK/cashflow")
    assert response.status_code == 200
    cf = response.json()
    assert len(cf) > 0
    assert "operating_activity" in cf[0]

def test_get_company_ratios():
    response = client.get("/api/v1/companies/HDFCBANK/ratios")
    assert response.status_code == 200
    ratios = response.json()
    assert len(ratios) > 0
    assert "return_on_equity_pct" in ratios[0]
    assert "debt_to_equity" in ratios[0]

def test_screener_presets():
    response = client.get("/api/v1/screener/presets")
    assert response.status_code == 200
    presets = response.json()
    assert isinstance(presets, list)
    assert "quality_compounder" in presets

def test_run_screener():
    response = client.get("/api/v1/screener?preset=quality_compounder")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should return matching companies
    if len(data) > 0:
        assert "company_id" in data[0]
        assert "composite_score" in data[0]

def test_run_screener_invalid_preset():
    response = client.get("/api/v1/screener?preset=invalid_preset_name")
    assert response.status_code == 400

def test_list_peer_groups():
    response = client.get("/api/v1/peers")
    assert response.status_code == 200
    groups = response.json()
    assert isinstance(groups, list)
    assert len(groups) > 0

def test_get_peer_group_details():
    response = client.get("/api/v1/peers")
    groups = response.json()
    first_group = groups[0]
    
    response = client.get(f"/api/v1/peers/{first_group}")
    assert response.status_code == 200
    details = response.json()
    assert isinstance(details, list)
    assert len(details) > 0
    assert "company_id" in details[0]
    assert "metrics" in details[0]

def test_get_peer_group_details_not_found():
    response = client.get("/api/v1/peers/INVALID_GROUP")
    assert response.status_code == 404

def test_list_sectors():
    response = client.get("/api/v1/sectors")
    assert response.status_code == 200
    sectors = response.json()
    assert isinstance(sectors, list)
    assert len(sectors) > 0
    assert "broad_sector" in sectors[0]
    assert "total_market_cap" in sectors[0]

def test_get_sector_constituents():
    response = client.get("/api/v1/sectors/Financials/constituents")
    assert response.status_code == 200
    constituents = response.json()
    assert isinstance(constituents, list)
    assert len(constituents) > 0
    assert constituents[0]["sub_sector"] is not None
