"""
Invoice Generator Database Initialization Script
Creates all tables and inserts default super admin.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import db_manager
from loguru import logger
import hashlib


async def create_default_admin():
    """Create a default super admin contractor account."""
    existing = await db_manager.fetch_one(
        "SELECT id FROM contractors WHERE email = ?", ("admin@invoicegen.com",)
    )
    if existing:
        logger.info("Default admin already exists, skipping...")
        return

    password_hash = hashlib.sha256("admin123".encode()).hexdigest()
    await db_manager.execute(
        """INSERT INTO contractors (company_name, owner_name, email, phone, address, role, password_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "Invoice Generator Admin",
            "System Admin",
            "admin@invoicegen.com",
            "000-000-0000",
            "System",
            "super_admin",
            password_hash,
        ),
    )
    logger.info("Default super admin created (admin@invoicegen.com / admin123)")


async def main():
    """Initialize database and seed data."""
    logger.info("=== Invoice Generator Database Initialization ===")

    # Create all tables
    await db_manager.initialize()

    # Create default admin
    await create_default_admin()

    logger.info("=== Database initialization complete ===")


if __name__ == "__main__":
    asyncio.run(main())
