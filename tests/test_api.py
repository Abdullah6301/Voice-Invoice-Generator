"""
Tests for API Endpoints
"""
import sys
import os
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestVoiceAPI:
    @pytest.mark.asyncio
    async def test_voice_text_input(self, client):
        resp = await client.post("/api/voice-input", json={"text": "Create an invoice for John Smith"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["intent"] == "create_invoice"

    @pytest.mark.asyncio
    async def test_voice_empty_text(self, client):
        resp = await client.post("/api/voice-input", json={"text": ""})
        assert resp.status_code in [200, 400, 422]


class TestCustomersAPI:
    @pytest.mark.asyncio
    async def test_list_customers(self, client):
        resp = await client.get("/api/customers")
        assert resp.status_code == 200
        data = resp.json()
        # API wraps in {"success": true, "customers": [...]}
        assert data.get("success") is True or isinstance(data, list)

    @pytest.mark.asyncio
    async def test_create_customer(self, client):
        resp = await client.post("/api/customers", json={
            "name": "API Test Customer",
            "email": "apitest@test.com",
            "phone": "555-0000"
        })
        assert resp.status_code == 200
        data = resp.json()
        # Could be wrapped or direct
        assert data.get("success") is True or data.get("name") == "API Test Customer"

    @pytest.mark.asyncio
    async def test_search_customers(self, client):
        await client.post("/api/customers", json={
            "name": "Searchable Person",
            "email": "search@test.com"
        })
        resp = await client.get("/api/customers?search=Searchable")
        assert resp.status_code == 200


class TestDatasetAPI:
    @pytest.mark.asyncio
    async def test_list_dataset(self, client):
        resp = await client.get("/api/dataset")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_categories(self, client):
        resp = await client.get("/api/dataset/categories")
        assert resp.status_code == 200


class TestInvoicesAPI:
    @pytest.mark.asyncio
    async def test_list_invoices(self, client):
        resp = await client.get("/api/invoices")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True or isinstance(data, list)


class TestDashboardPages:
    @pytest.mark.asyncio
    async def test_home_page(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "Invoice Generator" in resp.text

    @pytest.mark.asyncio
    async def test_customers_page(self, client):
        resp = await client.get("/customers-page")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_invoices_page(self, client):
        resp = await client.get("/invoices-page")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_dataset_page(self, client):
        resp = await client.get("/dataset-page")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_settings_page(self, client):
        resp = await client.get("/settings-page")
        assert resp.status_code == 200
