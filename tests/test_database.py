"""
Tests for Database Operations
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import DatabaseManager


TEST_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database", "test_invoice_generator.db"
)


@pytest.fixture(autouse=True)
async def db():
    """Create a fresh test database for each test."""
    # Clean up any previous test DB
    for ext in ["", "-wal", "-shm"]:
        p = TEST_DB_PATH + ext
        if os.path.exists(p):
            os.remove(p)

    mgr = DatabaseManager(TEST_DB_PATH)
    await mgr.initialize()
    yield mgr

    # Cleanup after test
    for ext in ["", "-wal", "-shm"]:
        p = TEST_DB_PATH + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


class TestDatabaseManager:
    @pytest.mark.asyncio
    async def test_insert_customer(self, db):
        cont_id = await db.execute_returning_id(
            "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("TestCo", "Admin", "admin@test.com", "hash", "admin")
        )
        cid = await db.execute_returning_id(
            "INSERT INTO customers (name, email, phone, contractor_id) VALUES (?, ?, ?, ?)",
            ("Test Customer", "test@test.com", "555-1234", cont_id)
        )
        assert cid is not None
        assert cid > 0

    @pytest.mark.asyncio
    async def test_fetch_customer(self, db):
        cont_id = await db.execute_returning_id(
            "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("TestCo", "Admin", "admin@test.com", "hash", "admin")
        )
        await db.execute(
            "INSERT INTO customers (name, email, phone, contractor_id) VALUES (?, ?, ?, ?)",
            ("Jane Doe", "jane@test.com", "555-5678", cont_id)
        )
        row = await db.fetch_one(
            "SELECT * FROM customers WHERE email = ?", ("jane@test.com",)
        )
        assert row is not None
        assert row["name"] == "Jane Doe"

    @pytest.mark.asyncio
    async def test_fetch_all_customers(self, db):
        cont_id = await db.execute_returning_id(
            "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("TestCo", "Admin", "admin@test.com", "hash", "admin")
        )
        for i in range(5):
            await db.execute(
                "INSERT INTO customers (name, email, contractor_id) VALUES (?, ?, ?)",
                (f"Customer {i}", f"c{i}@test.com", cont_id)
            )
        rows = await db.fetch_all("SELECT * FROM customers")
        assert len(rows) == 5

    @pytest.mark.asyncio
    async def test_insert_contractor(self, db):
        cid = await db.execute_returning_id(
            "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("TestCo", "Admin", "admin@test.com", "hashedpw", "admin")
        )
        assert cid > 0

    @pytest.mark.asyncio
    async def test_insert_invoice(self, db):
        cont_id = await db.execute_returning_id(
            "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("TestCo", "Admin", "a@test.com", "hash", "admin")
        )
        cust_id = await db.execute_returning_id(
            "INSERT INTO customers (name, contractor_id) VALUES (?, ?)", ("Test", cont_id)
        )
        inv_id = await db.execute_returning_id(
            "INSERT INTO invoices (invoice_number, customer_id, contractor_id, status, subtotal, tax_amount, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("INV-202501-0001", cust_id, cont_id, "draft", 100.0, 8.0, 108.0)
        )
        assert inv_id > 0

    @pytest.mark.asyncio
    async def test_insert_invoice_item(self, db):
        cont_id = await db.execute_returning_id(
            "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("TestCo", "Admin", "a@test.com", "hash", "admin")
        )
        cust_id = await db.execute_returning_id(
            "INSERT INTO customers (name, contractor_id) VALUES (?, ?)", ("Test", cont_id)
        )
        inv_id = await db.execute_returning_id(
            "INSERT INTO invoices (invoice_number, customer_id, contractor_id, status, subtotal, tax_amount, total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("INV-202501-0002", cust_id, cont_id, "draft", 0, 0, 0)
        )
        item_id = await db.execute_returning_id(
            "INSERT INTO invoice_items (invoice_id, item_name, quantity, unit, unit_price, total_price) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (inv_id, "Cedar Fencing", 100, "ft", 30.0, 3000.0)
        )
        assert item_id > 0

    @pytest.mark.asyncio
    async def test_dataset_item_insert(self, db):
        did = await db.execute_returning_id(
            "INSERT INTO dataset_items (item_name, category, unit, material_cost, labor_cost, total_price, csi_code) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Test Item", "Lumber", "ft", 5.0, 3.0, 8.0, "06 10 00")
        )
        assert did > 0

    @pytest.mark.asyncio
    async def test_update_customer(self, db):
        cont_id = await db.execute_returning_id(
            "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("TestCo", "Admin", "a@test.com", "hash", "admin")
        )
        cid = await db.execute_returning_id(
            "INSERT INTO customers (name, email, contractor_id) VALUES (?, ?, ?)",
            ("Old Name", "old@test.com", cont_id)
        )
        await db.execute(
            "UPDATE customers SET name = ? WHERE id = ?",
            ("New Name", cid)
        )
        row = await db.fetch_one("SELECT * FROM customers WHERE id = ?", (cid,))
        assert row["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_delete_customer(self, db):
        cont_id = await db.execute_returning_id(
            "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("TestCo", "Admin", "a@test.com", "hash", "admin")
        )
        cid = await db.execute_returning_id(
            "INSERT INTO customers (name, contractor_id) VALUES (?, ?)", ("ToDelete", cont_id)
        )
        await db.execute("DELETE FROM customers WHERE id = ?", (cid,))
        row = await db.fetch_one("SELECT * FROM customers WHERE id = ?", (cid,))
        assert row is None
