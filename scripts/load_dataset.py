"""
Invoice Generator Dataset Loader Script
Loads master_dataset.csv into SQLite database.
"""

import asyncio
import csv
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings
from database.connection import db_manager
from loguru import logger


async def load_dataset():
    """Load the CSV dataset into the dataset_items table."""
    csv_path = settings.DATASET_PATH

    if not Path(csv_path).exists():
        logger.error(f"Dataset file not found: {csv_path}")
        return

    logger.info(f"Loading dataset from {csv_path}")

    # Ensure tables exist
    await db_manager.initialize()

    count = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                await db_manager.execute(
                    """INSERT OR REPLACE INTO dataset_items
                       (item_id, category, item_name, unit, material_cost, labor_cost, total_price, csi_code)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        int(row["item_id"]),
                        row["category"],
                        row["item_name"],
                        row["unit"],
                        float(row["material_cost"]),
                        float(row["labor_cost"]),
                        float(row["total_price"]),
                        row["csi_code"],
                    ),
                )
                count += 1
            except Exception as e:
                logger.error(f"Error loading row {row}: {e}")

    logger.info(f"Successfully loaded {count} dataset items into database")


async def main():
    """Run dataset loading."""
    logger.info("=== Invoice Generator Dataset Loader ===")
    await load_dataset()

    # Verify
    items = await db_manager.fetch_all("SELECT COUNT(*) as count FROM dataset_items")
    logger.info(f"Total items in database: {items[0]['count']}")


if __name__ == "__main__":
    asyncio.run(main())
