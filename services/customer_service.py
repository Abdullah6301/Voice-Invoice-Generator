"""
Invoice Generator Customer Service
Handles all customer CRUD operations with SQLite.
"""

from datetime import datetime
from loguru import logger
from database.connection import db_manager


class CustomerService:
    """Customer management service with offline-first SQLite storage."""

    async def create_customer(self, contractor_id: int, name: str, **kwargs) -> dict:
        """
        Create a new customer record.

        Args:
            contractor_id: ID of the contractor who owns this customer
            name: Customer name
            **kwargs: Optional fields (phone, email, address, city, state, zip_code, notes)

        Returns:
            Created customer record as dict
        """
        customer_id = await db_manager.execute_returning_id(
            """INSERT INTO customers (contractor_id, name, phone, email, address, city, state, zip_code, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                contractor_id,
                name,
                kwargs.get("phone", ""),
                kwargs.get("email", ""),
                kwargs.get("address", ""),
                kwargs.get("city", ""),
                kwargs.get("state", ""),
                kwargs.get("zip_code", ""),
                kwargs.get("notes", ""),
            ),
        )

        # Log for sync
        await self._log_sync("customers", customer_id, "create")

        logger.info(f"Customer created: {name} (ID: {customer_id})")
        return await self.get_customer(customer_id)

    async def get_customer(self, customer_id: int) -> dict | None:
        """Get a customer by ID."""
        return await db_manager.fetch_one(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        )

    async def get_customers_by_contractor(self, contractor_id: int) -> list[dict]:
        """Get all customers for a contractor."""
        return await db_manager.fetch_all(
            "SELECT * FROM customers WHERE contractor_id = ? ORDER BY name",
            (contractor_id,),
        )

    async def search_customers(self, contractor_id: int, query: str) -> list[dict]:
        """Search customers by name, phone, or email."""
        return await db_manager.fetch_all(
            """SELECT * FROM customers
               WHERE contractor_id = ?
               AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)
               ORDER BY name""",
            (contractor_id, f"%{query}%", f"%{query}%", f"%{query}%"),
        )

    async def find_or_create_customer(self, contractor_id: int, name: str) -> dict:
        """
        Find existing customer by name or create a new one.
        Used by voice pipeline for automatic customer creation.
        """
        # Search for existing customer
        existing = await db_manager.fetch_one(
            "SELECT * FROM customers WHERE contractor_id = ? AND name LIKE ?",
            (contractor_id, f"%{name}%"),
        )
        if existing:
            logger.info(f"Found existing customer: {existing['name']}")
            return existing

        # Create new customer from voice input
        logger.info(f"Creating new customer from voice: {name}")
        return await self.create_customer(contractor_id, name)

    async def update_customer(self, customer_id: int, **kwargs) -> dict | None:
        """Update customer fields."""
        fields = []
        values = []
        for key in ["name", "phone", "email", "address", "city", "state", "zip_code", "notes"]:
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])

        if not fields:
            return await self.get_customer(customer_id)

        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(customer_id)

        await db_manager.execute(
            f"UPDATE customers SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )

        await self._log_sync("customers", customer_id, "update")
        logger.info(f"Customer updated: ID {customer_id}")
        return await self.get_customer(customer_id)

    async def delete_customer(self, customer_id: int) -> bool:
        """Delete a customer record."""
        await db_manager.execute(
            "DELETE FROM customers WHERE id = ?", (customer_id,)
        )
        await self._log_sync("customers", customer_id, "delete")
        logger.info(f"Customer deleted: ID {customer_id}")
        return True

    async def _log_sync(self, table: str, record_id: int, action: str):
        """Log a change for future cloud synchronization."""
        await db_manager.execute(
            """INSERT INTO sync_logs (table_name, record_id, action, status)
               VALUES (?, ?, ?, 'pending')""",
            (table, record_id, action),
        )


# Global instance
customer_service = CustomerService()
