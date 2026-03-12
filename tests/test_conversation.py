"""
Tests for Conversation Manager, Invoice Number Generation, and Conversational Flow.
Tests mock the Gemini API so they run without an API key.
"""
import sys
import os
import csv
import re
import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import DatabaseManager
from services.invoice_service import InvoiceService
from services.conversation_manager import (
    ConversationManager,
    ConversationState,
    FINISH_PHRASES,
)
from ai_engine.dataset_matcher import DatasetMatcher

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(PROJECT_ROOT, "dataset", "master_dataset.csv")
TEST_DB_PATH = os.path.join(PROJECT_ROOT, "database", "test_conversation.db")


def _load_csv_items():
    items = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append({
                    "item_id": int(row["item_id"]),
                    "item_name": row["item_name"],
                    "category": row["category"],
                    "unit": row["unit"],
                    "material_cost": float(row["material_cost"]),
                    "labor_cost": float(row["labor_cost"]),
                    "total_price": float(row["total_price"]),
                    "csi_code": row["csi_code"],
                })
    return items


def _load_dataset_matcher():
    matcher = DatasetMatcher()
    items = _load_csv_items()
    if items:
        matcher.dataset_items = items
        matcher.item_names = [i["item_name"] for i in items]
        matcher._loaded = True
    return matcher


# ── Invoice Number Generation Tests ──────────────────────────────────────


@pytest.fixture
async def test_db():
    """Create a fresh test database."""
    for ext in ["", "-wal", "-shm"]:
        p = TEST_DB_PATH + ext
        if os.path.exists(p):
            os.remove(p)

    mgr = DatabaseManager(TEST_DB_PATH)
    await mgr.initialize()
    yield mgr

    for ext in ["", "-wal", "-shm"]:
        p = TEST_DB_PATH + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


class TestInvoiceNumberGeneration:
    """Verify invoice number generation is always unique."""

    @pytest.mark.asyncio
    async def test_first_invoice_number(self, test_db):
        """Empty database should produce sequence 0001."""
        service = InvoiceService()
        # Monkey-patch to use test db
        import services.invoice_service as mod
        original = mod.db_manager
        mod.db_manager = test_db
        try:
            # Create contractor and customer
            cont_id = await test_db.execute_returning_id(
                "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) "
                "VALUES (?, ?, ?, ?, ?)",
                ("TestCo", "Admin", "a@test.com", "hash", "admin"),
            )
            cust_id = await test_db.execute_returning_id(
                "INSERT INTO customers (name, contractor_id) VALUES (?, ?)",
                ("Test Customer", cont_id),
            )
            inv = await service.create_invoice(cont_id, cust_id)
            assert inv["invoice_number"].endswith("-0001")
        finally:
            mod.db_manager = original

    @pytest.mark.asyncio
    async def test_sequential_invoice_numbers(self, test_db):
        """Multiple invoices should have sequential numbers."""
        service = InvoiceService()
        import services.invoice_service as mod
        original = mod.db_manager
        mod.db_manager = test_db
        try:
            cont_id = await test_db.execute_returning_id(
                "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) "
                "VALUES (?, ?, ?, ?, ?)",
                ("TestCo", "Admin", "b@test.com", "hash", "admin"),
            )
            cust_id = await test_db.execute_returning_id(
                "INSERT INTO customers (name, contractor_id) VALUES (?, ?)",
                ("Cust", cont_id),
            )

            numbers = []
            for _ in range(5):
                inv = await service.create_invoice(cont_id, cust_id)
                numbers.append(inv["invoice_number"])

            # Extract sequence numbers
            seqs = [int(n.rsplit("-", 1)[1]) for n in numbers]
            assert seqs == [1, 2, 3, 4, 5]
        finally:
            mod.db_manager = original

    @pytest.mark.asyncio
    async def test_uniqueness_after_deletion(self, test_db):
        """Deleting an invoice should not cause number reuse."""
        service = InvoiceService()
        import services.invoice_service as mod
        original = mod.db_manager
        mod.db_manager = test_db
        try:
            cont_id = await test_db.execute_returning_id(
                "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) "
                "VALUES (?, ?, ?, ?, ?)",
                ("TestCo", "Admin", "c@test.com", "hash", "admin"),
            )
            cust_id = await test_db.execute_returning_id(
                "INSERT INTO customers (name, contractor_id) VALUES (?, ?)",
                ("Cust", cont_id),
            )

            inv1 = await service.create_invoice(cont_id, cust_id)
            inv2 = await service.create_invoice(cont_id, cust_id)

            # Delete first invoice
            await service.delete_invoice(inv1["id"])

            # Create a new one — should NOT reuse "0001"
            inv3 = await service.create_invoice(cont_id, cust_id)
            assert inv3["invoice_number"] != inv1["invoice_number"]
            seq3 = int(inv3["invoice_number"].rsplit("-", 1)[1])
            assert seq3 == 3
        finally:
            mod.db_manager = original

    @pytest.mark.asyncio
    async def test_invoice_number_format(self, test_db):
        """Invoice number must follow INV-YYYYMM-NNNN format."""
        service = InvoiceService()
        import services.invoice_service as mod
        original = mod.db_manager
        mod.db_manager = test_db
        try:
            cont_id = await test_db.execute_returning_id(
                "INSERT INTO contractors (company_name, owner_name, email, password_hash, role) "
                "VALUES (?, ?, ?, ?, ?)",
                ("TestCo", "Admin", "d@test.com", "hash", "admin"),
            )
            cust_id = await test_db.execute_returning_id(
                "INSERT INTO customers (name, contractor_id) VALUES (?, ?)",
                ("Cust", cont_id),
            )
            inv = await service.create_invoice(cont_id, cust_id)
            pattern = r"^INV-\d{6}-\d{4}$"
            assert re.match(pattern, inv["invoice_number"]), \
                f"'{inv['invoice_number']}' does not match INV-YYYYMM-NNNN"
        finally:
            mod.db_manager = original


# ── Conversation State Tests ─────────────────────────────────────────────


class TestConversationState:
    """Test the ConversationState data structure."""

    def test_initial_missing_fields(self):
        state = ConversationState(contractor_id=1)
        missing = state.missing_required()
        assert "customer_name" in missing
        assert "project_location" in missing
        assert "material" in missing

    def test_customer_fills_gap(self):
        state = ConversationState(contractor_id=1)
        state.customer_name = "Mike Miller"
        missing = state.missing_required()
        assert "customer_name" not in missing
        assert "material" in missing

    def test_has_minimum(self):
        state = ConversationState(contractor_id=1)
        assert not state.has_minimum_for_invoice()
        state.customer_name = "Mike"
        assert not state.has_minimum_for_invoice()
        state.project_location = "West Oak"
        assert not state.has_minimum_for_invoice()
        state.items.append({"material": "Test", "quantity": 1, "unit": "each", "matched_item": {}})
        assert state.has_minimum_for_invoice()

    def test_to_dict(self):
        state = ConversationState(contractor_id=1)
        state.customer_name = "John"
        d = state.to_dict()
        assert d["customer_name"] == "John"
        assert d["phase"] == "init"


# ── Finish Phrase Detection Tests ────────────────────────────────────────


class TestFinishDetection:
    def setup_method(self):
        self.mgr = ConversationManager()

    def test_done_detected(self):
        assert self.mgr._is_finish_intent("done")

    def test_finish_order_detected(self):
        assert self.mgr._is_finish_intent("finish order")

    def test_thats_all_detected(self):
        assert self.mgr._is_finish_intent("that's all")

    def test_generate_invoice_detected(self):
        assert self.mgr._is_finish_intent("generate invoice")

    def test_complete_order_detected(self):
        assert self.mgr._is_finish_intent("complete order")

    def test_random_text_not_finish(self):
        assert not self.mgr._is_finish_intent("add more fencing")

    def test_nothing_else_detected(self):
        assert self.mgr._is_finish_intent("nothing else")


# ── Missing Field Detection Tests ────────────────────────────────────────


class TestMissingFieldDetection:
    def setup_method(self):
        self.mgr = ConversationManager()
        from ai_engine.dataset_matcher import dataset_matcher
        items = _load_csv_items()
        if items:
            dataset_matcher.dataset_items = items
            dataset_matcher.item_names = [i["item_name"] for i in items]
            dataset_matcher._loaded = True

    @pytest.mark.asyncio
    @patch("services.conversation_manager.gemini_parser")
    async def test_asks_for_customer(self, mock_parser):
        """If no customer name is found, system should ask for it."""
        mock_parser.parse_command = AsyncMock(return_value={
            "customer_name": None, "project_location": None, "items": []
        })
        result = await self.mgr.process_message(
            "add some fencing",
            contractor_id=1,
            session_id="test_missing_1",
        )
        assert "invoice for" in result["response"].lower() or "customer" in result["response"].lower()

    @pytest.mark.asyncio
    @patch("services.conversation_manager.gemini_parser")
    async def test_asks_for_location(self, mock_parser):
        """After customer name, system should ask for project location."""
        mock_parser.parse_command = AsyncMock(return_value={
            "customer_name": "Mike Miller", "project_location": None, "items": []
        })
        result = await self.mgr.process_message(
            "Create invoice for Mike Miller",
            contractor_id=1,
            session_id="test_missing_2",
        )
        assert "location" in result["response"].lower()

    @pytest.mark.asyncio
    @patch("services.conversation_manager.gemini_parser")
    async def test_asks_for_material(self, mock_parser):
        """After customer + location, should ask for material."""
        sid = "test_missing_3"
        mock_parser.parse_command = AsyncMock(return_value={
            "customer_name": "Mike Miller", "project_location": None, "items": []
        })
        await self.mgr.process_message("Create invoice for Mike Miller", 1, sid)

        mock_parser.parse_followup = AsyncMock(return_value={
            "customer_name": None, "project_location": "West Oak Site", "items": []
        })
        result = await self.mgr.process_message("West Oak Site", 1, sid)
        resp = result["response"].lower()
        assert "material" in resp


# ── Fuzzy Match / Product Confirmation Tests ─────────────────────────────


class TestProductMatchConfirmation:
    def setup_method(self):
        from ai_engine.dataset_matcher import dataset_matcher
        items = _load_csv_items()
        if items:
            dataset_matcher.dataset_items = items
            dataset_matcher.item_names = [i["item_name"] for i in items]
            dataset_matcher._loaded = True

    def test_fuzzy_misspelling(self):
        """Fuzzy matcher should handle misspellings."""
        from ai_engine.dataset_matcher import dataset_matcher
        # Use a close-enough misspelling
        result = dataset_matcher.match("cedar fense panel")
        assert result is not None
        assert "cedar" in result["item_name"].lower() or "fence" in result["item_name"].lower()

    def test_fuzzy_search_suggestions(self):
        """Search should return multiple suggestions."""
        from ai_engine.dataset_matcher import dataset_matcher
        results = dataset_matcher.search("cedar fence", limit=3)
        assert len(results) >= 1
        for r in results:
            assert "item_name" in r


# ── Conversation Flow Integration Tests ──────────────────────────────────


class TestConversationFlow:
    def setup_method(self):
        self.mgr = ConversationManager()
        from ai_engine.dataset_matcher import dataset_matcher
        items = _load_csv_items()
        if items:
            dataset_matcher.dataset_items = items
            dataset_matcher.item_names = [i["item_name"] for i in items]
            dataset_matcher._loaded = True

    @pytest.mark.asyncio
    @patch("services.conversation_manager.gemini_parser")
    async def test_full_conversation_flow(self, mock_parser):
        """Simulate a multi-turn conversation with mocked Gemini."""
        sid = "test_flow_1"

        # Step 1: User creates invoice with customer name
        mock_parser.parse_command = AsyncMock(return_value={
            "customer_name": "Mike Miller", "project_location": None, "items": []
        })
        r1 = await self.mgr.process_message("Create invoice for Mike Miller", 1, sid)
        state = self.mgr.get_or_create(1, sid)
        assert state.customer_name == "Mike Miller"
        assert "location" in r1["response"].lower()

        # Step 2: User provides location
        mock_parser.parse_followup = AsyncMock(return_value={
            "customer_name": None, "project_location": "West Oak Site", "items": []
        })
        r2 = await self.mgr.process_message("West Oak Site", 1, sid)
        assert state.project_location == "West Oak Site"
        assert "material" in r2["response"].lower()

        # Step 3: User provides material with quantity
        mock_parser.parse_followup = AsyncMock(return_value={
            "customer_name": None, "project_location": None,
            "items": [{"material_name": "Horizontal Cedar Fencing", "quantity": 100, "unit": "linear_ft", "extras": None}]
        })
        r3 = await self.mgr.process_message("100 feet of horizontal cedar fencing", 1, sid)
        assert len(state.items) >= 1

    @pytest.mark.asyncio
    @patch("services.conversation_manager.gemini_parser")
    async def test_full_command_single_message(self, mock_parser):
        """Full order in one message should extract all fields."""
        sid = "test_full_cmd"
        mock_parser.parse_command = AsyncMock(return_value={
            "customer_name": "Mike Miller",
            "project_location": "West Oak site",
            "items": [{"material_name": "Horizontal Cedar Fencing", "quantity": 100, "unit": "linear_ft", "extras": "smart lock gate"}]
        })
        r = await self.mgr.process_message(
            "Create invoice for Mike Miller at West Oak site. Add 100 feet cedar fencing with smart lock gate.",
            1, sid
        )
        state = self.mgr.get_or_create(1, sid)
        assert state.customer_name == "Mike Miller"
        assert state.project_location == "West Oak site"
        assert len(state.items) >= 1
        assert r["action"] == "ready"

    @pytest.mark.asyncio
    async def test_conversation_reset(self):
        """Resetting a session should clear state."""
        sid = "test_reset"
        state = self.mgr.get_or_create(1, sid)
        state.customer_name = "John"
        self.mgr.reset(1, sid)
        state = self.mgr.get_or_create(1, sid)
        assert state.customer_name is None
        assert state.phase == "init"

    @pytest.mark.asyncio
    @patch("services.conversation_manager.gemini_parser")
    async def test_finish_without_required_fields(self, mock_parser):
        """Saying 'done' without required info should prompt."""
        sid = "test_finish_early"
        mock_parser.parse_command = AsyncMock(return_value={
            "customer_name": "John", "project_location": None, "items": []
        })
        await self.mgr.process_message("Create invoice for John", 1, sid)
        state = self.mgr.get_or_create(1, sid)
        state.phase = "collecting"
        result = await self.mgr.process_message("done", 1, sid)
        assert result["action"] == "ask"

    @pytest.mark.asyncio
    @patch("services.conversation_manager.gemini_parser")
    async def test_short_quantity_response(self, mock_parser):
        """User responding with just '100' should be understood as quantity."""
        sid = "test_short_qty"
        # Set up state with customer + location + pending material
        state = self.mgr.get_or_create(1, sid)
        state.customer_name = "Mike"
        state.project_location = "Oak St"
        state.phase = "collecting"

        # First: add cedar fencing without quantity
        mock_parser.parse_command = AsyncMock(return_value={
            "customer_name": None, "project_location": None,
            "items": [{"material_name": "Horizontal Cedar Fencing", "quantity": None, "unit": None, "extras": None}]
        })
        r1 = await self.mgr.process_message("add cedar fencing", 1, sid)
        assert "how many" in r1["response"].lower()

        # Now respond with just "100"
        mock_parser.parse_followup = AsyncMock(return_value={
            "customer_name": None, "project_location": None,
            "items": [{"material_name": "Horizontal Cedar Fencing", "quantity": 100, "unit": "linear_ft", "extras": None}]
        })
        r2 = await self.mgr.process_message("100", 1, sid)
        assert len(state.items) >= 1
        assert state.items[-1]["quantity"] == 100


# ── Dataset Matching Tests ───────────────────────────────────────────────


class TestDatasetMatching:
    def setup_method(self):
        self.matcher = _load_dataset_matcher()

    def test_exact_match_cedar_fencing(self):
        result = self.matcher.match("Horizontal Cedar Fencing")
        assert result is not None
        assert result["item_name"] == "Horizontal Cedar Fencing"
        assert result["match_score"] == 100

    def test_fuzzy_match_partial_name(self):
        result = self.matcher.match("cedar fence panel")
        assert result is not None
        assert result["match_score"] >= 55

    def test_concrete_mix_match(self):
        result = self.matcher.match("concrete mix 80 pound bag")
        assert result is not None
        assert "concrete" in result["item_name"].lower()

    def test_no_match_nonsense(self):
        result = self.matcher.match("zlqwxptyb")
        assert result is None
