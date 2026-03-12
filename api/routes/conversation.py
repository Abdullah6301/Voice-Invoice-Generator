"""
Invoice Generator Conversation API Route
Handles multi-turn conversational ordering via voice or text.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from services.conversation_manager import conversation_manager
from services.customer_service import customer_service
from services.invoice_service import invoice_service

router = APIRouter()


class ConversationRequest(BaseModel):
    """Request body for a conversation message."""
    text: str
    contractor_id: int = 1
    session_id: str = "default"


class ConversationResetRequest(BaseModel):
    """Request body to reset a conversation session."""
    contractor_id: int = 1
    session_id: str = "default"


@router.post("/conversation")
async def conversation_message(request: ConversationRequest):
    """
    Process a conversational message.
    The system maintains state across messages and asks follow-up questions
    for missing information before generating an invoice.
    """
    try:
        result = await conversation_manager.process_message(
            text=request.text,
            contractor_id=request.contractor_id,
            session_id=request.session_id,
        )

        # If the conversation signals "create", generate the actual invoice
        if result.get("action") == "create":
            invoice_result = await _create_invoice_from_state(
                request.contractor_id, request.session_id
            )
            result["invoice"] = invoice_result.get("invoice")
            result["pdf_path"] = invoice_result.get("pdf_path")
            # Reset session after creation
            conversation_manager.reset(request.contractor_id, request.session_id)

        return {
            "success": True,
            "response": result.get("response", ""),
            "action": result.get("action", "ask"),
            "state": result.get("state", {}),
            "suggestions": result.get("suggestions", []),
            "invoice": result.get("invoice"),
            "pdf_path": result.get("pdf_path"),
        }

    except Exception as e:
        logger.error(f"Conversation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Could not process your message. Please try again.",
        )


@router.post("/conversation/reset")
async def reset_conversation(request: ConversationResetRequest):
    """Reset the current conversation session."""
    conversation_manager.reset(request.contractor_id, request.session_id)
    return {"success": True, "message": "Conversation reset. Ready for a new order."}


@router.get("/conversation/state")
async def get_conversation_state(contractor_id: int = 1, session_id: str = "default"):
    """Get the current conversation state for debugging / UI display."""
    state = conversation_manager.get_or_create(contractor_id, session_id)
    return {"success": True, "state": state.to_dict()}


async def _create_invoice_from_state(contractor_id: int, session_id: str) -> dict:
    """Create a real invoice from the completed conversation state."""
    state = conversation_manager.get_or_create(contractor_id, session_id)

    # Find or create customer
    customer = await customer_service.find_or_create_customer(
        contractor_id, state.customer_name
    )

    # Build notes from extras
    notes = ""
    if state.extras:
        notes = "Extras: " + ", ".join(state.extras)
    if state.notes:
        notes += f"\n{state.notes}" if notes else state.notes

    # Create invoice
    invoice = await invoice_service.create_invoice(
        contractor_id=contractor_id,
        customer_id=customer["id"],
        project_location=state.project_location or "",
        notes=notes,
    )

    # Add each item
    for item_data in state.items:
        matched = item_data.get("matched_item", {})
        await invoice_service.add_item(
            invoice_id=invoice["id"],
            item_name=item_data["material"],
            quantity=item_data["quantity"],
            unit_price=matched.get("total_price", 0),
            unit=item_data.get("unit", "each"),
            category=matched.get("category", ""),
            dataset_item_id=matched.get("item_id"),
            material_cost=matched.get("material_cost", 0),
            labor_cost=matched.get("labor_cost", 0),
        )

    # Finalize and generate PDF
    invoice = await invoice_service.finalize_invoice(invoice["id"])

    logger.info(
        f"Conversation invoice created: {invoice['invoice_number']} "
        f"for {state.customer_name}"
    )

    return {
        "invoice": invoice,
        "pdf_path": invoice.get("pdf_path"),
    }
