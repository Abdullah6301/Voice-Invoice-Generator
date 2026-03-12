"""
Invoice Generator Invoice API Routes
CRUD operations for invoices and invoice items.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from services.invoice_service import invoice_service

router = APIRouter()


class CreateInvoiceRequest(BaseModel):
    contractor_id: int = 1
    customer_id: int
    project_location: str = ""
    payment_terms: str = "Due on Receipt"
    notes: str = ""


class AddItemRequest(BaseModel):
    invoice_id: int
    item_name: str
    quantity: float = 1.0
    unit_price: float = 0.0
    unit: str = "each"
    category: str = ""
    description: str = ""
    dataset_item_id: int | None = None
    material_cost: float = 0.0
    labor_cost: float = 0.0


class RemoveItemRequest(BaseModel):
    invoice_id: int
    item_id: int


@router.post("/create-invoice")
async def create_invoice(request: CreateInvoiceRequest):
    """Create a new draft invoice."""
    try:
        invoice = await invoice_service.create_invoice(
            contractor_id=request.contractor_id,
            customer_id=request.customer_id,
            project_location=request.project_location,
            payment_terms=request.payment_terms,
            notes=request.notes,
        )
        return {"success": True, "invoice": invoice}
    except Exception as e:
        logger.error(f"Create invoice error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Invoice could not be created. Please try again.")


@router.post("/add-item")
async def add_item(request: AddItemRequest):
    """Add an item to an existing invoice."""
    try:
        item = await invoice_service.add_item(
            invoice_id=request.invoice_id,
            item_name=request.item_name,
            quantity=request.quantity,
            unit_price=request.unit_price,
            unit=request.unit,
            category=request.category,
            description=request.description,
            dataset_item_id=request.dataset_item_id,
            material_cost=request.material_cost,
            labor_cost=request.labor_cost,
        )
        invoice = await invoice_service.get_invoice(request.invoice_id)
        return {"success": True, "item": item, "invoice": invoice}
    except Exception as e:
        logger.error(f"Add item error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add item to invoice. Please try again.")


@router.post("/remove-item")
async def remove_item(request: RemoveItemRequest):
    """Remove an item from an invoice."""
    try:
        await invoice_service.remove_item(request.invoice_id, request.item_id)
        invoice = await invoice_service.get_invoice(request.invoice_id)
        return {"success": True, "invoice": invoice}
    except Exception as e:
        logger.error(f"Remove item error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove item from invoice. Please try again.")


@router.post("/finalize-invoice/{invoice_id}")
async def finalize_invoice(invoice_id: int):
    """Finalize an invoice and generate PDF."""
    try:
        invoice = await invoice_service.finalize_invoice(invoice_id)
        return {
            "success": True,
            "invoice": invoice,
            "pdf_path": invoice.get("pdf_path"),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Finalize invoice error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Invoice could not be finalized. Please try again.")


@router.get("/invoices")
async def list_invoices(contractor_id: int = 1):
    """List all invoices for a contractor."""
    try:
        invoices = await invoice_service.get_invoices_by_contractor(contractor_id)
        return {"success": True, "invoices": invoices}
    except Exception as e:
        logger.error(f"List invoices error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not load invoices. Please try again.")


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: int):
    """Get a specific invoice with its items."""
    invoice = await invoice_service.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"success": True, "invoice": invoice}


class UpdateInvoiceRequest(BaseModel):
    customer_id: int | None = None
    project_location: str | None = None
    notes: str | None = None
    payment_terms: str | None = None


class UpdateItemRequest(BaseModel):
    item_name: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    unit: str | None = None
    category: str | None = None
    description: str | None = None


@router.put("/invoices/{invoice_id}")
async def update_invoice(invoice_id: int, request: UpdateInvoiceRequest):
    """Update invoice details."""
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        invoice = await invoice_service.update_invoice(invoice_id, **updates)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"success": True, "invoice": invoice}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update invoice error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not update invoice. Please try again.")


@router.put("/invoice-items/{item_id}")
async def update_invoice_item(item_id: int, request: UpdateItemRequest):
    """Update an invoice item."""
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        item = await invoice_service.update_item(item_id, **updates)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        invoice = await invoice_service.get_invoice(item["invoice_id"])
        return {"success": True, "item": item, "invoice": invoice}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update item error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not update item. Please try again.")


@router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: int):
    """Delete an invoice."""
    try:
        await invoice_service.delete_invoice(invoice_id)
        return {"success": True, "message": "Invoice deleted"}
    except Exception as e:
        logger.error(f"Delete invoice error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not delete invoice. Please try again.")
