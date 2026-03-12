"""
Invoice Generator Invoice Service
Handles invoice creation, item management, and finalization with PDF generation.
"""

from datetime import datetime
from loguru import logger
from database.connection import db_manager
from invoices.pdf_generator import pdf_generator


class InvoiceService:
    """Invoice management service with full lifecycle support."""

    async def create_invoice(
        self,
        contractor_id: int,
        customer_id: int,
        project_location: str = "",
        payment_terms: str = "Due on Receipt",
        notes: str = "",
    ) -> dict:
        """
        Create a new draft invoice.

        Returns:
            Created invoice record as dict
        """
        invoice_number = await self._generate_invoice_number(contractor_id)

        invoice_id = await db_manager.execute_returning_id(
            """INSERT INTO invoices
               (invoice_number, contractor_id, customer_id, project_location,
                status, payment_terms, notes)
               VALUES (?, ?, ?, ?, 'draft', ?, ?)""",
            (invoice_number, contractor_id, customer_id, project_location,
             payment_terms, notes),
        )

        await self._log_sync("invoices", invoice_id, "create")
        logger.info(f"Invoice created: {invoice_number} (ID: {invoice_id})")
        return await self.get_invoice(invoice_id)

    async def get_invoice(self, invoice_id: int) -> dict | None:
        """Get invoice with all items."""
        invoice = await db_manager.fetch_one(
            "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
        )
        if not invoice:
            return None

        items = await db_manager.fetch_all(
            "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id",
            (invoice_id,),
        )
        invoice["items"] = items
        return invoice

    async def get_invoices_by_contractor(self, contractor_id: int) -> list[dict]:
        """Get all invoices for a contractor."""
        invoices = await db_manager.fetch_all(
            """SELECT i.*, c.name as customer_name
               FROM invoices i
               JOIN customers c ON i.customer_id = c.id
               WHERE i.contractor_id = ?
               ORDER BY i.created_at DESC""",
            (contractor_id,),
        )
        return invoices

    async def add_item(
        self,
        invoice_id: int,
        item_name: str,
        quantity: float,
        unit_price: float,
        unit: str = "each",
        category: str = "",
        description: str = "",
        dataset_item_id: int = None,
        material_cost: float = 0.0,
        labor_cost: float = 0.0,
    ) -> dict:
        """
        Add an item to an invoice.

        Returns:
            Created invoice item record
        """
        total_price = quantity * unit_price

        item_id = await db_manager.execute_returning_id(
            """INSERT INTO invoice_items
               (invoice_id, dataset_item_id, item_name, description, category,
                unit, quantity, unit_price, material_cost, labor_cost, total_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (invoice_id, dataset_item_id, item_name, description, category,
             unit, quantity, unit_price, material_cost, labor_cost, total_price),
        )

        # Recalculate invoice totals
        await self._recalculate_totals(invoice_id)

        logger.info(f"Item added to invoice {invoice_id}: {item_name} x{quantity} = ${total_price:.2f}")
        return await db_manager.fetch_one(
            "SELECT * FROM invoice_items WHERE id = ?", (item_id,)
        )

    async def remove_item(self, invoice_id: int, item_id: int) -> bool:
        """Remove an item from an invoice."""
        await db_manager.execute(
            "DELETE FROM invoice_items WHERE id = ? AND invoice_id = ?",
            (item_id, invoice_id),
        )
        await self._recalculate_totals(invoice_id)
        logger.info(f"Item {item_id} removed from invoice {invoice_id}")
        return True

    async def finalize_invoice(self, invoice_id: int) -> dict:
        """
        Finalize an invoice: set status, generate PDF.

        Returns:
            Updated invoice with PDF path
        """
        invoice = await self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Get contractor and customer info
        contractor = await db_manager.fetch_one(
            "SELECT * FROM contractors WHERE id = ?",
            (invoice["contractor_id"],),
        )
        customer = await db_manager.fetch_one(
            "SELECT * FROM customers WHERE id = ?",
            (invoice["customer_id"],),
        )

        if not contractor or not customer:
            raise ValueError("Contractor or customer not found")

        # Build PDF data
        pdf_data = {
            "invoice_number": invoice["invoice_number"],
            "date": datetime.now().strftime("%B %d, %Y"),
            "contractor": {
                "company_name": contractor["company_name"],
                "owner_name": contractor["owner_name"],
                "address": contractor.get("address", ""),
                "phone": contractor.get("phone", ""),
                "email": contractor.get("email", ""),
            },
            "customer": {
                "name": customer["name"],
                "address": customer.get("address", ""),
                "phone": customer.get("phone", ""),
                "email": customer.get("email", ""),
            },
            "project_location": invoice.get("project_location", ""),
            "items": [
                {
                    "item_name": item["item_name"],
                    "category": item.get("category", ""),
                    "quantity": item["quantity"],
                    "unit": item.get("unit", "each"),
                    "unit_price": item["unit_price"],
                    "total": item["total_price"],
                }
                for item in invoice["items"]
            ],
            "subtotal": invoice["subtotal"],
            "tax_rate": invoice["tax_rate"],
            "tax_amount": invoice["tax_amount"],
            "total": invoice["total"],
            "payment_terms": invoice.get("payment_terms", "Due on Receipt"),
            "notes": invoice.get("notes", ""),
        }

        # Generate PDF
        pdf_path = pdf_generator.generate(pdf_data)

        # Update invoice status
        await db_manager.execute(
            """UPDATE invoices
               SET status = 'finalized', pdf_path = ?, updated_at = ?
               WHERE id = ?""",
            (pdf_path, datetime.now().isoformat(), invoice_id),
        )

        await self._log_sync("invoices", invoice_id, "finalize")
        logger.info(f"Invoice {invoice['invoice_number']} finalized. PDF: {pdf_path}")

        return await self.get_invoice(invoice_id)

    async def save_draft(self, invoice_id: int) -> dict:
        """Save invoice as draft."""
        await db_manager.execute(
            "UPDATE invoices SET status = 'draft', updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), invoice_id),
        )
        logger.info(f"Invoice {invoice_id} saved as draft")
        return await self.get_invoice(invoice_id)

    async def _recalculate_totals(self, invoice_id: int):
        """Recalculate invoice subtotal, tax, and total."""
        result = await db_manager.fetch_one(
            "SELECT COALESCE(SUM(total_price), 0) as subtotal FROM invoice_items WHERE invoice_id = ?",
            (invoice_id,),
        )
        subtotal = result["subtotal"] if result else 0.0

        invoice = await db_manager.fetch_one(
            "SELECT tax_rate FROM invoices WHERE id = ?", (invoice_id,)
        )
        tax_rate = invoice["tax_rate"] if invoice else 0.0
        tax_amount = subtotal * (tax_rate / 100)
        total = subtotal + tax_amount

        await db_manager.execute(
            """UPDATE invoices
               SET subtotal = ?, tax_amount = ?, total = ?, updated_at = ?
               WHERE id = ?""",
            (subtotal, tax_amount, total, datetime.now().isoformat(), invoice_id),
        )

    async def _generate_invoice_number(self, contractor_id: int) -> str:
        """
        Generate a unique invoice number with format INV-YYYYMM-NNNN.
        Handles: empty database, month changes, deleted invoices, concurrent requests.
        """
        date_prefix = datetime.now().strftime("%Y%m")
        pattern = f"INV-{date_prefix}-%"

        # Find the highest sequence number for the current month
        result = await db_manager.fetch_one(
            """SELECT invoice_number FROM invoices
               WHERE invoice_number LIKE ?
               ORDER BY invoice_number DESC LIMIT 1""",
            (pattern,),
        )

        if result and result["invoice_number"]:
            try:
                last_seq = int(result["invoice_number"].rsplit("-", 1)[1])
            except (ValueError, IndexError):
                last_seq = 0
        else:
            last_seq = 0

        next_seq = last_seq + 1
        invoice_number = f"INV-{date_prefix}-{next_seq:04d}"

        # Safety: if the generated number already exists (concurrent race), keep incrementing
        while True:
            exists = await db_manager.fetch_one(
                "SELECT 1 FROM invoices WHERE invoice_number = ?",
                (invoice_number,),
            )
            if not exists:
                break
            next_seq += 1
            invoice_number = f"INV-{date_prefix}-{next_seq:04d}"

        return invoice_number

    async def update_invoice(self, invoice_id: int, **kwargs) -> dict | None:
        """Update invoice fields (customer, location, notes, payment_terms)."""
        allowed = ["customer_id", "project_location", "notes", "payment_terms"]
        fields = []
        values = []
        for key in allowed:
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        if not fields:
            return await self.get_invoice(invoice_id)
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(invoice_id)
        await db_manager.execute(
            f"UPDATE invoices SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        # Re-finalize if already finalized (regenerate PDF)
        invoice = await self.get_invoice(invoice_id)
        if invoice and invoice.get("status") == "finalized":
            invoice = await self.finalize_invoice(invoice_id)
        logger.info(f"Invoice {invoice_id} updated")
        return invoice

    async def update_item(self, item_id: int, **kwargs) -> dict | None:
        """Update an invoice item's fields."""
        allowed = ["item_name", "quantity", "unit_price", "unit", "category", "description"]
        fields = []
        values = []
        for key in allowed:
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        if not fields:
            return await db_manager.fetch_one("SELECT * FROM invoice_items WHERE id = ?", (item_id,))
        # Recalculate total_price if quantity or unit_price changed
        item = await db_manager.fetch_one("SELECT * FROM invoice_items WHERE id = ?", (item_id,))
        if not item:
            return None
        qty = kwargs.get("quantity", item["quantity"])
        price = kwargs.get("unit_price", item["unit_price"])
        total = qty * price
        fields.append("total_price = ?")
        values.append(total)
        values.append(item_id)
        await db_manager.execute(
            f"UPDATE invoice_items SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        await self._recalculate_totals(item["invoice_id"])
        # Re-finalize if needed
        invoice = await self.get_invoice(item["invoice_id"])
        if invoice and invoice.get("status") == "finalized":
            await self.finalize_invoice(item["invoice_id"])
        return await db_manager.fetch_one("SELECT * FROM invoice_items WHERE id = ?", (item_id,))

    async def delete_invoice(self, invoice_id: int) -> bool:
        """Delete an invoice and all its items."""
        await db_manager.execute(
            "DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,)
        )
        await db_manager.execute(
            "DELETE FROM invoices WHERE id = ?", (invoice_id,)
        )
        await self._log_sync("invoices", invoice_id, "delete")
        logger.info(f"Invoice {invoice_id} deleted")
        return True

    async def _log_sync(self, table: str, record_id: int, action: str):
        """Log a change for future cloud synchronization."""
        await db_manager.execute(
            """INSERT INTO sync_logs (table_name, record_id, action, status)
               VALUES (?, ?, ?, 'pending')""",
            (table, record_id, action),
        )


# Global instance
invoice_service = InvoiceService()
