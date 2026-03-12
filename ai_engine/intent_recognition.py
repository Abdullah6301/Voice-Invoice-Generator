"""
Invoice Generator Intent Recognition Engine
Classifies user commands into action intents using rule-based NLP + spaCy.
"""

import re
from loguru import logger


# Intent definitions with keyword patterns
INTENT_PATTERNS = {
    "create_invoice": {
        "keywords": [
            r"\bcreate\b.*\binvoice\b",
            r"\bnew\b.*\binvoice\b",
            r"\bstart\b.*\binvoice\b",
            r"\bmake\b.*\binvoice\b",
            r"\bgenerate\b.*\binvoice\b",
            r"\binvoice\b.*\bfor\b",
        ],
        "priority": 1,
    },
    "add_item": {
        "keywords": [
            r"\badd\b",
            r"\binclude\b",
            r"\bput\b.*\bin\b",
            r"\binsert\b",
            r"\b\d+\b.*\b(feet|foot|ft|pieces|units|yards|sheets|bags|boxes|gallons|rolls|each|sqft|sq ft|square feet|linear feet|hours|hour)\b",
        ],
        "priority": 2,
    },
    "remove_item": {
        "keywords": [
            r"\bremove\b",
            r"\bdelete\b",
            r"\btake\s+out\b",
            r"\bcancel\b.*\bitem\b",
            r"\bget\s+rid\b",
        ],
        "priority": 3,
    },
    "finalize_invoice": {
        "keywords": [
            r"\bfinalize\b",
            r"\bcomplete\b.*\binvoice\b",
            r"\bfinish\b.*\binvoice\b",
            r"\bclose\b.*\binvoice\b",
            r"\bsend\b.*\binvoice\b",
            r"\bgenerate\b.*\bpdf\b",
            r"\bexport\b",
        ],
        "priority": 4,
    },
    "save_draft": {
        "keywords": [
            r"\bsave\b",
            r"\bdraft\b",
            r"\bkeep\b",
            r"\bstore\b",
            r"\bsave\b.*\bdraft\b",
        ],
        "priority": 5,
    },
}


class IntentRecognizer:
    """
    Rule-based intent recognition for construction voice commands.
    Classifies text input into predefined intents.
    """

    def __init__(self):
        self.patterns = {}
        for intent, config in INTENT_PATTERNS.items():
            compiled = [re.compile(p, re.IGNORECASE) for p in config["keywords"]]
            self.patterns[intent] = {
                "compiled": compiled,
                "priority": config["priority"],
            }
        logger.info("Intent recognizer initialized with rule-based patterns")

    def recognize(self, text: str) -> dict:
        """
        Recognize intent from text input.

        Args:
            text: Transcribed text from speech

        Returns:
            Dict with 'intent', 'confidence', and 'matched_pattern'
        """
        if not text or not text.strip():
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "matched_pattern": None,
            }

        text_lower = text.lower().strip()
        matches = []

        for intent, config in self.patterns.items():
            for pattern in config["compiled"]:
                if pattern.search(text_lower):
                    matches.append({
                        "intent": intent,
                        "priority": config["priority"],
                        "pattern": pattern.pattern,
                    })
                    break  # One match per intent is enough

        if not matches:
            # Default: if text mentions quantities and materials, assume add_item
            if re.search(r"\b\d+\b", text_lower):
                logger.info(f"Defaulting to 'add_item' for text with numbers: '{text}'")
                return {
                    "intent": "add_item",
                    "confidence": 0.5,
                    "matched_pattern": "default_number_match",
                }

            # If text mentions a person's name with "for", assume create_invoice
            if re.search(r"\bfor\b\s+[A-Z]", text):
                return {
                    "intent": "create_invoice",
                    "confidence": 0.5,
                    "matched_pattern": "default_for_name_match",
                }

            return {
                "intent": "unknown",
                "confidence": 0.3,
                "matched_pattern": None,
            }

        # Sort by priority (lower = higher priority)
        matches.sort(key=lambda x: x["priority"])
        best = matches[0]

        # Calculate confidence based on number of matching intents
        confidence = 0.9 if len(matches) == 1 else 0.7

        result = {
            "intent": best["intent"],
            "confidence": confidence,
            "matched_pattern": best["pattern"],
        }

        logger.info(f"Intent recognized: {result['intent']} (confidence: {result['confidence']:.2f})")
        return result


# Global instance
intent_recognizer = IntentRecognizer()
