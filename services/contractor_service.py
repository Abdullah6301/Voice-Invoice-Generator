"""
Invoice Generator Contractor Service
Handles contractor profile management and authentication.
"""

import hashlib
from datetime import datetime
from loguru import logger
from database.connection import db_manager


class ContractorService:
    """Contractor account management service."""

    async def create_contractor(
        self,
        company_name: str,
        owner_name: str,
        email: str,
        password: str,
        phone: str = "",
        address: str = "",
        role: str = "contractor_admin",
    ) -> dict:
        """Register a new contractor account."""
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        contractor_id = await db_manager.execute_returning_id(
            """INSERT INTO contractors
               (company_name, owner_name, email, phone, address, role, password_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (company_name, owner_name, email, phone, address, role, password_hash),
        )

        logger.info(f"Contractor created: {company_name} (ID: {contractor_id})")
        return await self.get_contractor(contractor_id)

    async def get_contractor(self, contractor_id: int) -> dict | None:
        """Get contractor by ID."""
        return await db_manager.fetch_one(
            "SELECT id, company_name, owner_name, email, phone, address, logo_path, "
            "business_license, specialty, role, created_at FROM contractors WHERE id = ?",
            (contractor_id,),
        )

    async def authenticate(self, email: str, password: str) -> dict | None:
        """Authenticate a contractor by email and password."""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        contractor = await db_manager.fetch_one(
            """SELECT id, company_name, owner_name, email, role
               FROM contractors WHERE email = ? AND password_hash = ?""",
            (email, password_hash),
        )
        if contractor:
            logger.info(f"Contractor authenticated: {email}")
        else:
            logger.warning(f"Authentication failed: {email}")
        return contractor

    async def update_contractor(self, contractor_id: int, **kwargs) -> dict | None:
        """Update contractor profile fields."""
        allowed = ["company_name", "owner_name", "email", "phone", "address",
                    "logo_path", "business_license", "specialty"]
        fields = []
        values = []
        for key in allowed:
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])

        if not fields:
            return await self.get_contractor(contractor_id)

        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(contractor_id)

        await db_manager.execute(
            f"UPDATE contractors SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        logger.info(f"Contractor updated: ID {contractor_id}")
        return await self.get_contractor(contractor_id)

    async def get_all_contractors(self) -> list[dict]:
        """Get all contractors (super admin use)."""
        return await db_manager.fetch_all(
            "SELECT id, company_name, owner_name, email, phone, role, created_at "
            "FROM contractors ORDER BY company_name"
        )


# Global instance
contractor_service = ContractorService()
