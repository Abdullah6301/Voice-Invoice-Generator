"""
Invoice Generator Voice API Routes
Handles voice input processing (audio and text).
"""

import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from loguru import logger

from services.voice_command_service import voice_command_service

router = APIRouter()


class TextCommandRequest(BaseModel):
    """Request body for text-based voice commands."""
    text: str
    contractor_id: int = 1
    current_invoice_id: int | None = None


class TextCommandResponse(BaseModel):
    """Response for voice command processing."""
    success: bool
    message: str
    intent: str | None = None
    invoice: dict | None = None
    customer: dict | None = None
    items_added: int | None = None
    pdf_path: str | None = None


@router.post("/voice-input", response_model=TextCommandResponse)
async def process_voice_input(request: TextCommandRequest):
    """
    Process a voice command (as text) through the AI pipeline.

    This endpoint accepts text input (simulating transcribed voice)
    and processes it through intent recognition, NER, and dataset matching.
    """
    try:
        result = await voice_command_service.process_text_command(
            text=request.text,
            contractor_id=request.contractor_id,
            current_invoice_id=request.current_invoice_id,
        )
        return TextCommandResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            intent=result.get("intent"),
            invoice=result.get("invoice"),
            customer=result.get("customer"),
            items_added=result.get("items_added"),
            pdf_path=result.get("pdf_path"),
        )
    except Exception as e:
        logger.error(f"Voice input error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Voice command could not be processed. Please try again.")


@router.post("/voice-upload")
async def upload_voice_file(
    audio: UploadFile = File(...),
    contractor_id: int = Form(default=1),
    current_invoice_id: int = Form(default=None),
):
    """
    Upload an audio file (WAV) for voice command processing.

    The audio is transcribed and processed through the full AI pipeline.
    """
    try:
        # Save uploaded file temporarily
        suffix = ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Process audio through pipeline
        result = await voice_command_service.process_audio_command(
            audio_path=tmp_path,
            contractor_id=contractor_id,
            current_invoice_id=current_invoice_id,
        )

        # Clean up temp file
        os.unlink(tmp_path)

        return result

    except Exception as e:
        logger.error(f"Voice upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Audio processing failed. Please try again.")
