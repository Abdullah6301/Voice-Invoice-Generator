"""
Invoice Generator Dataset API Routes
Browse and manage the construction materials dataset.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from services.dataset_service import dataset_service

router = APIRouter()


class AddDatasetItemRequest(BaseModel):
    category: str
    item_name: str
    unit: str
    material_cost: float
    labor_cost: float
    total_price: float
    csi_code: str = ""


class SetPriceOverrideRequest(BaseModel):
    contractor_id: int
    item_id: int
    material_cost: float | None = None
    labor_cost: float | None = None
    total_price: float | None = None


@router.get("/dataset")
async def list_dataset(category: str = None, search: str = None):
    """List dataset items, optionally filtered by category or search query."""
    try:
        if search:
            items = await dataset_service.search_items(search)
        elif category:
            items = await dataset_service.get_all_items(category=category)
        else:
            items = await dataset_service.get_all_items()
        return {"success": True, "items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"List dataset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dataset/categories")
async def list_categories():
    """Get all dataset categories."""
    try:
        categories = await dataset_service.get_categories()
        return {"success": True, "categories": categories}
    except Exception as e:
        logger.error(f"List categories error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dataset/{item_id}")
async def get_dataset_item(item_id: int):
    """Get a specific dataset item."""
    item = await dataset_service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True, "item": item}


@router.post("/dataset")
async def add_dataset_item(request: AddDatasetItemRequest):
    """Add a new item to the dataset (super admin)."""
    try:
        item = await dataset_service.add_item(request.model_dump())
        return {"success": True, "item": item}
    except Exception as e:
        logger.error(f"Add dataset item error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class UpdateDatasetItemRequest(BaseModel):
    category: str | None = None
    item_name: str | None = None
    unit: str | None = None
    material_cost: float | None = None
    labor_cost: float | None = None
    total_price: float | None = None
    csi_code: str | None = None


@router.put("/dataset/{item_id}")
async def update_dataset_item(item_id: int, request: UpdateDatasetItemRequest):
    """Update a dataset item."""
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        item = await dataset_service.update_item(item_id, updates)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"success": True, "item": item}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update dataset item error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/dataset/{item_id}")
async def delete_dataset_item(item_id: int):
    """Delete a dataset item."""
    try:
        item = await dataset_service.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        await dataset_service.delete_item(item_id)
        return {"success": True, "message": "Item deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete dataset item error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dataset/price-override")
async def set_price_override(request: SetPriceOverrideRequest):
    """Set a contractor-specific pricing override for a dataset item."""
    try:
        result = await dataset_service.set_contractor_price(
            contractor_id=request.contractor_id,
            item_id=request.item_id,
            material_cost=request.material_cost,
            labor_cost=request.labor_cost,
            total_price=request.total_price,
        )
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Set price override error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
