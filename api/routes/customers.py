"""
Invoice Generator Customer API Routes
CRUD operations for customer management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from services.customer_service import customer_service

router = APIRouter()


class CreateCustomerRequest(BaseModel):
    contractor_id: int = 1
    name: str
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    notes: str = ""


class UpdateCustomerRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    notes: str | None = None


@router.get("/customers")
async def list_customers(contractor_id: int = 1, search: str = None):
    """List all customers for a contractor, with optional search."""
    try:
        if search:
            customers = await customer_service.search_customers(contractor_id, search)
        else:
            customers = await customer_service.get_customers_by_contractor(contractor_id)
        return {"success": True, "customers": customers}
    except Exception as e:
        logger.error(f"List customers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customers/{customer_id}")
async def get_customer(customer_id: int):
    """Get a specific customer."""
    customer = await customer_service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"success": True, "customer": customer}


@router.post("/customers")
async def create_customer(request: CreateCustomerRequest):
    """Create a new customer."""
    try:
        customer = await customer_service.create_customer(
            contractor_id=request.contractor_id,
            name=request.name,
            phone=request.phone,
            email=request.email,
            address=request.address,
            city=request.city,
            state=request.state,
            zip_code=request.zip_code,
            notes=request.notes,
        )
        return {"success": True, "customer": customer}
    except Exception as e:
        logger.error(f"Create customer error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/customers/{customer_id}")
async def update_customer(customer_id: int, request: UpdateCustomerRequest):
    """Update a customer's information."""
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        customer = await customer_service.update_customer(customer_id, **updates)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return {"success": True, "customer": customer}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update customer error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: int):
    """Delete a customer."""
    try:
        await customer_service.delete_customer(customer_id)
        return {"success": True, "message": "Customer deleted"}
    except Exception as e:
        logger.error(f"Delete customer error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
