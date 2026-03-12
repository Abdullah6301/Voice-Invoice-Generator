"""
Invoice Generator Dataset Service
Handles dataset querying and contractor pricing overrides.
"""

from loguru import logger
from database.connection import db_manager


class DatasetService:
    """Dataset management service."""

    async def get_all_items(self, category: str = None) -> list[dict]:
        """Get all dataset items, optionally filtered by category."""
        if category:
            return await db_manager.fetch_all(
                "SELECT * FROM dataset_items WHERE category = ? ORDER BY item_name",
                (category,),
            )
        return await db_manager.fetch_all(
            "SELECT * FROM dataset_items ORDER BY category, item_name"
        )

    async def get_item(self, item_id: int) -> dict | None:
        """Get a single dataset item by ID."""
        return await db_manager.fetch_one(
            "SELECT * FROM dataset_items WHERE item_id = ?", (item_id,)
        )

    async def search_items(self, query: str) -> list[dict]:
        """Search dataset items by name or category."""
        return await db_manager.fetch_all(
            """SELECT * FROM dataset_items
               WHERE item_name LIKE ? OR category LIKE ?
               ORDER BY item_name""",
            (f"%{query}%", f"%{query}%"),
        )

    async def get_categories(self) -> list[str]:
        """Get all unique categories."""
        rows = await db_manager.fetch_all(
            "SELECT DISTINCT category FROM dataset_items ORDER BY category"
        )
        return [row["category"] for row in rows]

    async def add_item(self, item_data: dict) -> dict:
        """Add a new item to the dataset (super admin)."""
        item_id = await db_manager.execute_returning_id(
            """INSERT INTO dataset_items
               (category, item_name, unit, material_cost, labor_cost, total_price, csi_code)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                item_data["category"],
                item_data["item_name"],
                item_data["unit"],
                item_data["material_cost"],
                item_data["labor_cost"],
                item_data["total_price"],
                item_data.get("csi_code", ""),
            ),
        )
        logger.info(f"Dataset item added: {item_data['item_name']} (ID: {item_id})")
        return await self.get_item(item_id)

    async def update_item(self, item_id: int, item_data: dict) -> dict | None:
        """Update a dataset item (super admin)."""
        fields = []
        values = []
        for key in ["category", "item_name", "unit", "material_cost",
                     "labor_cost", "total_price", "csi_code"]:
            if key in item_data:
                fields.append(f"{key} = ?")
                values.append(item_data[key])

        if fields:
            values.append(item_id)
            await db_manager.execute(
                f"UPDATE dataset_items SET {', '.join(fields)} WHERE item_id = ?",
                tuple(values),
            )
            logger.info(f"Dataset item updated: ID {item_id}")

        return await self.get_item(item_id)

    async def delete_item(self, item_id: int) -> bool:
        """Delete a dataset item."""
        await db_manager.execute(
            "DELETE FROM dataset_items WHERE item_id = ?", (item_id,)
        )
        logger.info(f"Dataset item deleted: ID {item_id}")
        return True

    async def set_contractor_price(
        self, contractor_id: int, item_id: int,
        material_cost: float = None, labor_cost: float = None,
        total_price: float = None,
    ) -> dict:
        """Set a contractor-specific pricing override."""
        await db_manager.execute(
            """INSERT INTO contractor_pricing
               (contractor_id, dataset_item_id, custom_material_cost,
                custom_labor_cost, custom_total_price)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(contractor_id, dataset_item_id)
               DO UPDATE SET
                custom_material_cost = excluded.custom_material_cost,
                custom_labor_cost = excluded.custom_labor_cost,
                custom_total_price = excluded.custom_total_price""",
            (contractor_id, item_id, material_cost, labor_cost, total_price),
        )
        logger.info(f"Custom pricing set for contractor {contractor_id}, item {item_id}")
        return {"contractor_id": contractor_id, "item_id": item_id, "status": "updated"}

    async def get_item_price_for_contractor(self, contractor_id: int, item_id: int) -> dict:
        """Get the effective price for an item, considering contractor overrides."""
        # Check for contractor-specific pricing
        override = await db_manager.fetch_one(
            """SELECT * FROM contractor_pricing
               WHERE contractor_id = ? AND dataset_item_id = ?""",
            (contractor_id, item_id),
        )

        item = await self.get_item(item_id)
        if not item:
            return None

        if override:
            if override.get("custom_material_cost") is not None:
                item["material_cost"] = override["custom_material_cost"]
            if override.get("custom_labor_cost") is not None:
                item["labor_cost"] = override["custom_labor_cost"]
            if override.get("custom_total_price") is not None:
                item["total_price"] = override["custom_total_price"]
            item["is_custom_price"] = True
        else:
            item["is_custom_price"] = False

        return item


# Global instance
dataset_service = DatasetService()
