"""
Invoice Generator Voice Command Service
Orchestrates voice command processing: pipeline → service actions.
"""

from loguru import logger
from ai_engine.pipeline import voice_pipeline
from ai_engine.dataset_matcher import dataset_matcher
from services.customer_service import customer_service
from services.invoice_service import invoice_service
from database.connection import db_manager


class VoiceCommandService:
    """
    Processes voice commands end-to-end:
    1. Run AI pipeline (STT → Intent → NER → Match)
    2. Execute business action based on intent
    3. Return structured result
    """

    def __init__(self):
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure dataset matcher is loaded."""
        if not self._initialized:
            await dataset_matcher.load_dataset(db_manager)
            self._initialized = True

    async def process_text_command(self, text: str, contractor_id: int, current_invoice_id: int = None) -> dict:
        """
        Process a text command (or transcribed voice) and execute the appropriate action.

        Args:
            text: Voice command as text
            contractor_id: ID of the authenticated contractor
            current_invoice_id: ID of the currently active invoice (for add/remove item)

        Returns:
            Result dict with action taken and data
        """
        await self._ensure_initialized()

        # Run AI pipeline
        pipeline_result = await voice_pipeline.process_text(text)

        if not pipeline_result["success"]:
            return {
                "success": False,
                "message": pipeline_result["summary"],
                "pipeline": pipeline_result,
            }

        intent = pipeline_result["intent"]["intent"]
        entities = pipeline_result["entities"]
        matched_items = pipeline_result["matched_items"]

        # Execute action based on intent
        if intent == "create_invoice":
            return await self._handle_create_invoice(
                contractor_id, entities, matched_items
            )
        elif intent == "add_item":
            return await self._handle_add_item(
                contractor_id, current_invoice_id, entities, matched_items
            )
        elif intent == "remove_item":
            return await self._handle_remove_item(
                current_invoice_id, entities
            )
        elif intent == "finalize_invoice":
            return await self._handle_finalize_invoice(current_invoice_id)
        elif intent == "save_draft":
            return await self._handle_save_draft(current_invoice_id)
        else:
            return {
                "success": True,
                "message": f"Command understood but no action taken. Intent: {intent}",
                "intent": intent,
                "pipeline": pipeline_result,
            }

    async def process_audio_command(self, audio_path: str, contractor_id: int, current_invoice_id: int = None) -> dict:
        """Process an audio file through the full pipeline."""
        await self._ensure_initialized()

        pipeline_result = await voice_pipeline.process_audio(audio_path)
        if not pipeline_result["success"]:
            return {
                "success": False,
                "message": "Failed to process audio",
                "pipeline": pipeline_result,
            }

        # Re-process through text command handler
        return await self.process_text_command(
            pipeline_result["text"], contractor_id, current_invoice_id
        )

    async def _handle_create_invoice(self, contractor_id: int, entities: dict, matched_items: list) -> dict:
        """Handle create_invoice intent."""
        customer_name = entities.get("customer_name", "Walk-in Customer")
        location = entities.get("location", "")

        # Find or create customer
        customer = await customer_service.find_or_create_customer(
            contractor_id, customer_name
        )

        # Create invoice
        invoice = await invoice_service.create_invoice(
            contractor_id=contractor_id,
            customer_id=customer["id"],
            project_location=location,
        )

        # Add matched items to invoice
        items_added = []
        for item_data in matched_items:
            if item_data.get("matched_item"):
                match = item_data["matched_item"]
                added = await invoice_service.add_item(
                    invoice_id=invoice["id"],
                    item_name=match["item_name"],
                    quantity=item_data["quantity"],
                    unit_price=match["total_price"],
                    unit=match.get("unit", item_data.get("unit", "each")),
                    category=match.get("category", ""),
                    dataset_item_id=match.get("item_id"),
                    material_cost=match.get("material_cost", 0),
                    labor_cost=match.get("labor_cost", 0),
                )
                items_added.append(added)

        # Refresh invoice with items
        invoice = await invoice_service.get_invoice(invoice["id"])

        logger.info(f"Voice invoice created: {invoice['invoice_number']} for {customer_name}")

        return {
            "success": True,
            "message": f"Invoice {invoice['invoice_number']} created for {customer_name}",
            "intent": "create_invoice",
            "invoice": invoice,
            "customer": customer,
            "items_added": len(items_added),
        }

    async def _handle_add_item(self, contractor_id: int, invoice_id: int, entities: dict, matched_items: list) -> dict:
        """Handle add_item intent."""
        if not invoice_id:
            return {
                "success": False,
                "message": "No active invoice. Create an invoice first.",
                "intent": "add_item",
            }

        items_added = []
        for item_data in matched_items:
            if item_data.get("matched_item"):
                match = item_data["matched_item"]
                added = await invoice_service.add_item(
                    invoice_id=invoice_id,
                    item_name=match["item_name"],
                    quantity=item_data["quantity"],
                    unit_price=match["total_price"],
                    unit=match.get("unit", item_data.get("unit", "each")),
                    category=match.get("category", ""),
                    dataset_item_id=match.get("item_id"),
                    material_cost=match.get("material_cost", 0),
                    labor_cost=match.get("labor_cost", 0),
                )
                items_added.append(added)

        invoice = await invoice_service.get_invoice(invoice_id)
        return {
            "success": True,
            "message": f"{len(items_added)} item(s) added to invoice",
            "intent": "add_item",
            "invoice": invoice,
            "items_added": len(items_added),
        }

    async def _handle_remove_item(self, invoice_id: int, entities: dict) -> dict:
        """Handle remove_item intent."""
        if not invoice_id:
            return {
                "success": False,
                "message": "No active invoice.",
                "intent": "remove_item",
            }

        # Try to find matching item in invoice
        invoice = await invoice_service.get_invoice(invoice_id)
        if not invoice or not invoice.get("items"):
            return {
                "success": False,
                "message": "Invoice has no items to remove.",
                "intent": "remove_item",
            }

        # Match materials mentioned to invoice items
        removed_count = 0
        for material in entities.get("materials", []):
            for item in invoice["items"]:
                if material.lower() in item["item_name"].lower():
                    await invoice_service.remove_item(invoice_id, item["id"])
                    removed_count += 1
                    break

        # If no material match, remove the last item
        if removed_count == 0 and invoice["items"]:
            last_item = invoice["items"][-1]
            await invoice_service.remove_item(invoice_id, last_item["id"])
            removed_count = 1

        invoice = await invoice_service.get_invoice(invoice_id)
        return {
            "success": True,
            "message": f"{removed_count} item(s) removed from invoice",
            "intent": "remove_item",
            "invoice": invoice,
        }

    async def _handle_finalize_invoice(self, invoice_id: int) -> dict:
        """Handle finalize_invoice intent."""
        if not invoice_id:
            return {
                "success": False,
                "message": "No active invoice to finalize.",
                "intent": "finalize_invoice",
            }

        invoice = await invoice_service.finalize_invoice(invoice_id)
        return {
            "success": True,
            "message": f"Invoice {invoice['invoice_number']} finalized. PDF generated.",
            "intent": "finalize_invoice",
            "invoice": invoice,
            "pdf_path": invoice.get("pdf_path"),
        }

    async def _handle_save_draft(self, invoice_id: int) -> dict:
        """Handle save_draft intent."""
        if not invoice_id:
            return {
                "success": False,
                "message": "No active invoice to save.",
                "intent": "save_draft",
            }

        invoice = await invoice_service.save_draft(invoice_id)
        return {
            "success": True,
            "message": f"Invoice {invoice['invoice_number']} saved as draft.",
            "intent": "save_draft",
            "invoice": invoice,
        }


# Global instance
voice_command_service = VoiceCommandService()
