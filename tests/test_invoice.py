"""
Tests for Invoice Generation (PDF)
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from invoices.pdf_generator import InvoicePDFGenerator


class TestPDFGenerator:
    def setup_method(self):
        self.gen = InvoicePDFGenerator()
        self.output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "invoices", "output"
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def _sample_invoice_data(self, **overrides):
        data = {
            "invoice_number": "INV-TEST-0001",
            "date": "January 15, 2025",
            "contractor": {
                "company_name": "Invoice Generator Corp",
                "owner_name": "Admin",
                "address": "123 Main St",
                "phone": "555-0000",
                "email": "admin@bv.com",
            },
            "customer": {
                "name": "Mike Miller",
                "address": "West Oak Site",
                "phone": "555-1111",
                "email": "mike@test.com",
            },
            "project_location": "West Oak Site",
            "items": [
                {
                    "item_name": "Horizontal Cedar Fencing",
                    "description": "Cedar fencing material",
                    "quantity": 100,
                    "unit": "ft",
                    "unit_price": 30.00,
                    "total": 3000.00,
                },
            ],
            "subtotal": 3000.00,
            "tax_rate": 0.08,
            "tax_amount": 240.00,
            "total": 3240.00,
            "payment_terms": "Net 30",
            "notes": "Test invoice",
        }
        data.update(overrides)
        return data

    def test_generate_pdf(self):
        path = self.gen.generate(self._sample_invoice_data())
        assert path is not None
        assert os.path.exists(path)
        assert path.endswith(".pdf")
        os.remove(path)

    def test_pdf_filename_format(self):
        path = self.gen.generate(self._sample_invoice_data())
        filename = os.path.basename(path)
        assert filename.startswith("INV-TEST-0001")
        os.remove(path)

    def test_pdf_with_no_items(self):
        path = self.gen.generate(self._sample_invoice_data(items=[]))
        assert os.path.exists(path)
        os.remove(path)

    def test_pdf_with_multiple_items(self):
        items = [
            {"item_name": "Cedar Fencing", "description": "", "quantity": 100, "unit": "ft", "unit_price": 30.00, "total": 3000.00},
            {"item_name": "Concrete Mix", "description": "", "quantity": 20, "unit": "bag", "unit_price": 12.00, "total": 240.00},
            {"item_name": "Drywall Sheet", "description": "", "quantity": 50, "unit": "sheet", "unit_price": 15.00, "total": 750.00},
        ]
        path = self.gen.generate(self._sample_invoice_data(
            items=items, subtotal=3990.00, tax_amount=319.20, total=4309.20
        ))
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
        os.remove(path)
