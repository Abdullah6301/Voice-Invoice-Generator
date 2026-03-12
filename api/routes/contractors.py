"""
Invoice Generator Contractor API Routes
Contractor profile management and authentication.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from services.contractor_service import contractor_service
from services.auth_service import set_auth_cookie

router = APIRouter()


class RegisterRequest(BaseModel):
    company_name: str
    owner_name: str
    email: str
    password: str
    phone: str = ""
    address: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateProfileRequest(BaseModel):
    company_name: str | None = None
    owner_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    business_license: str | None = None
    specialty: str | None = None


@router.post("/contractors/register")
async def register_contractor(request: RegisterRequest):
    """Register a new contractor account."""
    try:
        contractor = await contractor_service.create_contractor(
            company_name=request.company_name,
            owner_name=request.owner_name,
            email=request.email,
            password=request.password,
            phone=request.phone,
            address=request.address,
        )
        response = JSONResponse(content={"success": True, "contractor": contractor})
        set_auth_cookie(response, contractor["id"], contractor["email"])
        return response
    except Exception as e:
        logger.error(f"Register contractor error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/contractors/login")
async def login_contractor(request: LoginRequest):
    """Authenticate a contractor."""
    contractor = await contractor_service.authenticate(request.email, request.password)
    if not contractor:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    response = JSONResponse(content={"success": True, "contractor": contractor})
    set_auth_cookie(response, contractor["id"], contractor["email"])
    return response


@router.get("/contractors/me")
async def get_current_contractor(request_obj: Request):
    """Get the currently authenticated contractor from JWT cookie."""
    from services.auth_service import get_current_user
    user = get_current_user(request_obj)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    contractor = await contractor_service.get_contractor(user["sub"])
    if not contractor:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return {"success": True, "contractor": contractor}


@router.get("/contractors/{contractor_id}")
async def get_contractor(contractor_id: int):
    """Get contractor profile."""
    contractor = await contractor_service.get_contractor(contractor_id)
    if not contractor:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return {"success": True, "contractor": contractor}


@router.put("/contractors/{contractor_id}")
async def update_contractor(contractor_id: int, request: UpdateProfileRequest):
    """Update contractor profile."""
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        contractor = await contractor_service.update_contractor(contractor_id, **updates)
        if not contractor:
            raise HTTPException(status_code=404, detail="Contractor not found")
        return {"success": True, "contractor": contractor}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update contractor error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contractors")
async def list_contractors():
    """List all contractors (super admin)."""
    try:
        contractors = await contractor_service.get_all_contractors()
        return {"success": True, "contractors": contractors}
    except Exception as e:
        logger.error(f"List contractors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
