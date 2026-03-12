"""
Invoice Generator AI Parser
Uses Groq API (LLaMA) to extract structured invoice data from natural language.
"""

import json
import re
from groq import Groq
from loguru import logger

from backend.config import settings

# System prompt that instructs the model how to parse invoice commands
SYSTEM_PROMPT = """You are an AI assistant for a construction invoice system called Invoice Generator.
Your job is to extract structured invoice information from natural language input.

You must return ONLY valid JSON with this exact structure:
{
  "customer_name": "string or null",
  "project_location": "string or null",
  "items": [
    {
      "material_name": "string",
      "quantity": number or null,
      "unit": "string or null",
      "extras": "string or null"
    }
  ]
}

Rules:
- Extract customer name, project location, and all materials mentioned.
- If the user says "for Mike Miller", customer_name is "Mike Miller".
- If the user says "at West Oak site", project_location is "West Oak site".
- Material names should be cleaned and normalized (e.g. "cedar fencing" -> "Cedar Fencing").
- Quantity should be a number. If no quantity is given, set it to null.
- Unit examples: "feet", "bags", "each", "sq_ft", "linear_ft", "gallon", "sheets", "rolls".
- Extras are additional features like "smart lock gate", "solid stain", etc.
- If no customer or location is mentioned, set them to null.
- If the input is just a number (like "100"), treat it as a quantity answer.
- If the input is a short answer to a previous question, extract what you can.
- Always return valid JSON. No markdown, no explanation, just the JSON object.
"""

FOLLOWUP_PROMPT = """You are an AI assistant for a construction invoice system.
The system previously asked the user a question. The user has now responded.

Previous question: {question}
Current conversation state: {state}
User response: {user_text}

Extract any information from the user's response and return ONLY valid JSON:
{{
  "customer_name": "string or null",
  "project_location": "string or null",
  "items": [
    {{
      "material_name": "string",
      "quantity": number or null,
      "unit": "string or null",
      "extras": "string or null"
    }}
  ]
}}

Rules:
- If the user is answering a question about customer name, put their answer in customer_name.
- If the user is answering a question about location, put their answer in project_location.
- If the user is answering about quantity (e.g. just "100" or "100 feet"), extract the quantity and unit.
- If the user is naming a material, put it in items[].material_name.
- For short answers like just a number, interpret it based on the previous question context.
- Always return valid JSON. No markdown, no explanation.
"""


class GeminiParser:
    """Parses natural language into structured invoice data using Groq API."""

    def __init__(self):
        self._client = None
        self._configured = False

    def _ensure_configured(self):
        """Configure the Groq API on first use."""
        if self._configured:
            return

        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Add it to your .env file."
            )

        self._client = Groq(api_key=api_key)
        self._configured = True
        logger.info("Groq API configured successfully")

    async def parse_command(self, text: str) -> dict:
        """
        Parse a natural language invoice command into structured data.

        Args:
            text: User's natural language input

        Returns:
            Parsed dict with customer_name, project_location, items[]
        """
        self._ensure_configured()

        try:
            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,
                max_tokens=1024,
            )
            raw = response.choices[0].message.content.strip()
            parsed = self._extract_json(raw)
            logger.info(f"Groq parsed: {json.dumps(parsed, default=str)}")
            return parsed
        except Exception as e:
            logger.error(f"Groq parse error: {e}")
            return self._empty_result()

    async def parse_followup(self, user_text: str, question: str, state: dict) -> dict:
        """
        Parse a follow-up response in context of a previous question.

        Args:
            user_text: The user's response
            question: The question AI asked before
            state: Current conversation state dict

        Returns:
            Parsed dict with extracted fields
        """
        self._ensure_configured()

        state_summary = json.dumps(state, default=str)
        followup_context = FOLLOWUP_PROMPT.format(
            question=question,
            state=state_summary,
            user_text=user_text,
        )

        try:
            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": followup_context},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.1,
                max_tokens=1024,
            )
            raw = response.choices[0].message.content.strip()
            parsed = self._extract_json(raw)
            logger.info(f"Groq followup parsed: {json.dumps(parsed, default=str)}")
            return parsed
        except Exception as e:
            logger.error(f"Groq followup parse error: {e}")
            return self._empty_result()

    def _extract_json(self, raw: str) -> dict:
        """Extract JSON from Gemini's response, handling markdown fences."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse Gemini response: {raw[:200]}")
                    return self._empty_result()
            else:
                logger.warning(f"No JSON found in Gemini response: {raw[:200]}")
                return self._empty_result()

        # Validate and normalize the structure
        return self._normalize(result)

    def _normalize(self, data: dict) -> dict:
        """Ensure the parsed data has the expected structure."""
        result = {
            "customer_name": data.get("customer_name") or None,
            "project_location": data.get("project_location") or None,
            "items": [],
        }

        items = data.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("material_name"):
                    result["items"].append({
                        "material_name": item["material_name"],
                        "quantity": item.get("quantity"),
                        "unit": item.get("unit"),
                        "extras": item.get("extras"),
                    })

        return result

    def _empty_result(self) -> dict:
        return {
            "customer_name": None,
            "project_location": None,
            "items": [],
        }


# Global instance
gemini_parser = GeminiParser()
