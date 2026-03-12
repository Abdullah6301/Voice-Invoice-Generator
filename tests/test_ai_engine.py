"""
Tests for AI Engine - Intent Recognition, NER, Dataset Matching, Pipeline
"""
import sys
import os
import csv
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_engine.intent_recognition import IntentRecognizer
from ai_engine.ner_engine import NEREngine
from ai_engine.dataset_matcher import DatasetMatcher

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(PROJECT_ROOT, "dataset", "master_dataset.csv")


def _load_csv_items():
    """Helper to load dataset items from CSV into matcher-compatible format."""
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


# ── Intent Recognition Tests ──────────────────────────────────────────────

class TestIntentRecognition:
    def setup_method(self):
        self.recognizer = IntentRecognizer()

    def test_create_invoice_intent(self):
        result = self.recognizer.recognize("Create an invoice for Mike Miller")
        assert result["intent"] == "create_invoice"
        assert result["confidence"] > 0.0

    def test_create_invoice_new_keyword(self):
        result = self.recognizer.recognize("New invoice for customer")
        assert result["intent"] == "create_invoice"

    def test_add_item_intent(self):
        result = self.recognizer.recognize("Add 50 feet of cedar fencing")
        assert result["intent"] == "add_item"

    def test_add_item_include_keyword(self):
        result = self.recognizer.recognize("Include concrete blocks in the invoice")
        assert result["intent"] == "add_item"

    def test_remove_item_intent(self):
        result = self.recognizer.recognize("Remove the fencing from the invoice")
        assert result["intent"] == "remove_item"

    def test_finalize_intent(self):
        result = self.recognizer.recognize("Finalize the invoice and generate PDF")
        assert result["intent"] == "finalize_invoice"

    def test_save_draft_intent(self):
        result = self.recognizer.recognize("Save this as a draft")
        assert result["intent"] == "save_draft"

    def test_unknown_intent(self):
        result = self.recognizer.recognize("What is the weather today?")
        # Unknown input should have low confidence
        assert result["confidence"] <= 0.5

    def test_empty_input(self):
        result = self.recognizer.recognize("")
        assert result["intent"] == "unknown"

    def test_case_insensitive(self):
        result = self.recognizer.recognize("CREATE AN INVOICE for someone")
        assert result["intent"] == "create_invoice"


# ── NER Engine Tests ──────────────────────────────────────────────────────

class TestNEREngine:
    def setup_method(self):
        self.ner = NEREngine()

    def test_customer_name_extraction(self):
        entities = self.ner.extract_entities("Create an invoice for Mike Miller")
        assert entities["customer_name"] == "Mike Miller"

    def test_location_extraction(self):
        entities = self.ner.extract_entities("Invoice for someone at West Oak Site")
        assert entities["location"] is not None
        assert "West Oak" in entities["location"]

    def test_quantity_extraction_feet(self):
        entities = self.ner.extract_entities("Add 100 feet of cedar fencing")
        assert len(entities["quantities"]) > 0
        qty = entities["quantities"][0]
        assert qty["value"] == 100
        assert qty["unit"] == "linear_ft"

    def test_quantity_extraction_sqft(self):
        entities = self.ner.extract_entities("Add 500 square feet of drywall")
        assert len(entities["quantities"]) > 0
        qty = entities["quantities"][0]
        assert qty["value"] == 500
        assert qty["unit"] == "sq_ft"

    def test_quantity_extraction_bags(self):
        entities = self.ner.extract_entities("Add 20 bags of concrete mix")
        assert len(entities["quantities"]) > 0
        qty = entities["quantities"][0]
        assert qty["value"] == 20
        # bags are normalized to "each" in the NER unit patterns
        assert qty["unit"] == "each"

    def test_feature_extraction(self):
        entities = self.ner.extract_entities("Add fencing with smart lock gate")
        assert len(entities["features"]) > 0
        assert "smart lock gate" in entities["features"]

    def test_full_prd_example(self):
        text = ("Create an invoice for Mike Miller at West Oak Site. "
                "Add 100 feet of horizontal cedar fencing with smart lock gate and solid stain.")
        entities = self.ner.extract_entities(text)
        assert entities["customer_name"] is not None
        assert len(entities["quantities"]) > 0

    def test_empty_input(self):
        entities = self.ner.extract_entities("")
        assert entities["customer_name"] is None
        assert entities["location"] is None
        assert len(entities["quantities"]) == 0


# ── Dataset Matcher Tests ─────────────────────────────────────────────────

class TestDatasetMatcher:
    def setup_method(self):
        self.matcher = DatasetMatcher()
        # Load dataset from CSV directly into matcher internals
        items = _load_csv_items()
        if items:
            self.matcher.dataset_items = items
            self.matcher.item_names = [item["item_name"] for item in items]
            self.matcher._loaded = True

    def test_exact_match(self):
        result = self.matcher.match("Horizontal Cedar Fencing")
        assert result is not None
        assert "cedar" in result["item_name"].lower()

    def test_fuzzy_match(self):
        result = self.matcher.match("cedar fence")
        assert result is not None
        assert result["match_score"] > 50

    def test_concrete_match(self):
        result = self.matcher.match("concrete mix")
        assert result is not None
        assert "concrete" in result["item_name"].lower()

    def test_no_match(self):
        result = self.matcher.match("quantum computer")
        # May or may not match - if score is below threshold, should be None
        if result:
            assert result["match_score"] >= 55  # default threshold

    def test_search(self):
        results = self.matcher.search("lumber")
        assert len(results) > 0
        for r in results:
            assert r["match_score"] > 0

    def test_match_multiple(self):
        results = self.matcher.match_multiple(["concrete", "lumber", "fencing"])
        assert len(results) == 3

    def test_empty_input(self):
        result = self.matcher.match("")
        assert result is None


# ── Pipeline Integration Test (async) ─────────────────────────────────────

class TestPipeline:
    @pytest.fixture(autouse=True)
    def setup_pipeline(self):
        """Load dataset items into the pipeline's matcher."""
        from ai_engine.pipeline import voice_pipeline
        self.pipeline = voice_pipeline
        items = _load_csv_items()
        if items:
            self.pipeline.matcher.dataset_items = items
            self.pipeline.matcher.item_names = [i["item_name"] for i in items]
            self.pipeline.matcher._loaded = True

    @pytest.mark.asyncio
    async def test_full_pipeline_text(self):
        result = await self.pipeline.process_text(
            "Create an invoice for Mike Miller at West Oak Site. "
            "Add 100 feet of horizontal cedar fencing."
        )
        assert result["success"] is True
        assert result["intent"]["intent"] == "create_invoice"
        assert len(result["matched_items"]) > 0
        assert result["matched_items"][0]["quantity"] == 100

    @pytest.mark.asyncio
    async def test_pipeline_add_item(self):
        result = await self.pipeline.process_text(
            "Add 50 bags of concrete mix"
        )
        assert result["success"] is True
        assert result["intent"]["intent"] == "add_item"
        assert len(result["matched_items"]) > 0

    @pytest.mark.asyncio
    async def test_pipeline_unknown(self):
        result = await self.pipeline.process_text(
            "What time is the meeting?"
        )
        assert result["success"] is True
        # Should not be a construction intent
        assert result["intent"]["confidence"] <= 0.5

    @pytest.mark.asyncio
    async def test_pipeline_summary(self):
        result = await self.pipeline.process_text(
            "Create an invoice for John Smith. Add 200 sqft of drywall."
        )
        assert "summary" in result
        assert len(result["summary"]) > 0
