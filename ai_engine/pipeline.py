"""
Invoice Generator Voice Processing Pipeline
Orchestrates: Voice → STT → Intent → NER → Dataset Match → Invoice Action
"""

from loguru import logger
from ai_engine.speech_to_text import stt_engine
from ai_engine.intent_recognition import intent_recognizer
from ai_engine.ner_engine import ner_engine
from ai_engine.dataset_matcher import dataset_matcher


class VoicePipeline:
    """
    Main voice processing pipeline that chains together:
    1. Speech-to-Text
    2. Intent Recognition
    3. Named Entity Recognition
    4. Dataset Matching
    """

    def __init__(self):
        self.stt = stt_engine
        self.intent = intent_recognizer
        self.ner = ner_engine
        self.matcher = dataset_matcher
        logger.info("Voice pipeline initialized")

    async def process_audio(self, audio_path: str) -> dict:
        """
        Process an audio file through the complete pipeline.

        Args:
            audio_path: Path to WAV audio file

        Returns:
            Pipeline result with text, intent, entities, and matched items
        """
        logger.info(f"Processing audio file: {audio_path}")

        # Step 1: Speech to Text
        text = self.stt.transcribe_audio_file(audio_path)
        if not text:
            return self._error_result("Failed to transcribe audio")

        return await self._process_text_pipeline(text)

    async def process_text(self, text: str) -> dict:
        """
        Process text input through the pipeline (for text commands or testing).

        Args:
            text: Text command to process

        Returns:
            Pipeline result with intent, entities, and matched items
        """
        logger.info(f"Processing text input: '{text}'")
        processed_text = self.stt.transcribe_text_input(text)
        return await self._process_text_pipeline(processed_text)

    async def _process_text_pipeline(self, text: str) -> dict:
        """Core pipeline processing after text is available."""

        # Step 2: Intent Recognition
        intent_result = self.intent.recognize(text)

        # Step 3: Named Entity Recognition
        entities = self.ner.extract_entities(text)

        # Step 4: Dataset Matching
        matched_items = []
        if entities["quantities"]:
            for qty_info in entities["quantities"]:
                match = self.matcher.match(qty_info["material_text"])
                matched_items.append({
                    "quantity": qty_info["value"],
                    "unit": qty_info["unit"],
                    "input_text": qty_info["material_text"],
                    "matched_item": match,
                    "total_price": (
                        match["total_price"] * qty_info["value"]
                        if match else 0.0
                    ),
                })
        elif entities["materials"]:
            # Try to match materials without explicit quantities
            for mat in entities["materials"]:
                match = self.matcher.match(mat)
                matched_items.append({
                    "quantity": 1,
                    "unit": "each",
                    "input_text": mat,
                    "matched_item": match,
                    "total_price": match["total_price"] if match else 0.0,
                })

        # Build result
        result = {
            "success": True,
            "text": text,
            "intent": intent_result,
            "entities": entities,
            "matched_items": matched_items,
            "summary": self._build_summary(intent_result, entities, matched_items),
        }

        logger.info(f"Pipeline complete - Intent: {intent_result['intent']}, "
                    f"Items matched: {len(matched_items)}")

        return result

    def _build_summary(self, intent: dict, entities: dict, matched_items: list) -> str:
        """Build a human-readable summary of the pipeline result."""
        parts = [f"Intent: {intent['intent']}"]

        if entities["customer_name"]:
            parts.append(f"Customer: {entities['customer_name']}")
        if entities["location"]:
            parts.append(f"Location: {entities['location']}")

        if matched_items:
            total = sum(item["total_price"] for item in matched_items)
            parts.append(f"Items: {len(matched_items)}, Estimated Total: ${total:.2f}")

        return " | ".join(parts)

    def _error_result(self, message: str) -> dict:
        """Return an error result."""
        logger.error(f"Pipeline error: {message}")
        return {
            "success": False,
            "text": "",
            "intent": {"intent": "unknown", "confidence": 0.0},
            "entities": {
                "customer_name": None,
                "location": None,
                "materials": [],
                "quantities": [],
                "features": [],
                "raw_text": "",
            },
            "matched_items": [],
            "summary": f"Error: {message}",
        }


# Global pipeline instance
voice_pipeline = VoicePipeline()
