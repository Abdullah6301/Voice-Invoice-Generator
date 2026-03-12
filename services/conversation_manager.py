"""
Invoice Generator Conversation Manager
Manages multi-turn invoice ordering using Gemini AI for parsing.
Handles state tracking, dataset matching, missing field detection, and invoice creation.
"""

import re
from datetime import datetime
from loguru import logger

from ai_engine.gemini_parser import gemini_parser
from ai_engine.dataset_matcher import dataset_matcher


# Phrases that signal the user wants to finalize the order
FINISH_PHRASES = [
    r"\bdone\b",
    r"\bfinish\s*(the\s+)?order\b",
    r"\bthat'?s?\s+all\b",
    r"\bgenerate\s+invoice\b",
    r"\bcomplete\s*(the\s+)?order\b",
    r"\bfinalize\b",
    r"\bno\s*,?\s*that'?s?\s*(it|all)\b",
    r"\bnothing\s+else\b",
    r"\bwe'?re\s+done\b",
    r"\bgo\s+ahead\b",
    r"\bsubmit\b",
    r"\bcreate\s+it\b",
    r"\byes\s*,?\s+generate\b",
]


class ConversationState:
    """Holds the state of a single ordering conversation."""

    def __init__(self, contractor_id: int):
        self.contractor_id = contractor_id
        self.customer_name: str | None = None
        self.project_location: str | None = None
        self.items: list[dict] = []  # [{material, quantity, unit, matched_item}]
        self.extras: list[str] = []
        self.notes: str | None = None
        self.pending_confirmation: dict | None = None  # fuzzy match confirmation
        self.last_question: str | None = None  # tracks what we last asked
        self.awaiting_field: str | None = None  # "customer_name" | "project_location" | "quantity" | "material"
        self.phase: str = "init"  # init | collecting | confirming | done
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "customer_name": self.customer_name,
            "project_location": self.project_location,
            "items": self.items,
            "extras": self.extras,
            "notes": self.notes,
            "phase": self.phase,
        }

    def missing_required(self) -> list[str]:
        """Return list of required fields still missing."""
        missing = []
        if not self.customer_name:
            missing.append("customer_name")
        if not self.project_location:
            missing.append("project_location")
        if not self.items:
            missing.append("material")
        return missing

    def has_minimum_for_invoice(self) -> bool:
        """Check if we have enough to generate an invoice."""
        return bool(self.customer_name and self.project_location and self.items)


class ConversationManager:
    """
    Manages conversational ordering sessions.
    Uses Gemini AI to parse user input and extract structured data.
    """

    def __init__(self):
        self._sessions: dict[str, ConversationState] = {}

    def get_or_create(self, contractor_id: int, session_id: str) -> ConversationState:
        key = f"{contractor_id}:{session_id}"
        if key not in self._sessions:
            self._sessions[key] = ConversationState(contractor_id)
            logger.info(f"New conversation session: {key}")
        return self._sessions[key]

    def reset(self, contractor_id: int, session_id: str):
        key = f"{contractor_id}:{session_id}"
        self._sessions.pop(key, None)
        logger.info(f"Conversation session reset: {key}")

    async def process_message(self, text: str, contractor_id: int, session_id: str) -> dict:
        """
        Process a user message within a conversation context.

        Returns dict with: response, state, action, suggestions, invoice
        """
        state = self.get_or_create(contractor_id, session_id)

        # Check if user wants to finish
        if self._is_finish_intent(text) and state.phase == "collecting":
            return await self._handle_finish(state, contractor_id, session_id)

        # Handle pending fuzzy match confirmation (user selecting 1/2/3)
        if state.pending_confirmation:
            return await self._handle_confirmation(text, state)

        # Use Gemini to parse the message
        if state.awaiting_field and state.last_question:
            parsed = await gemini_parser.parse_followup(
                user_text=text,
                question=state.last_question,
                state=state.to_dict(),
            )
        else:
            parsed = await gemini_parser.parse_command(text)

        # Update state with parsed data
        self._update_state(state, parsed)

        # Process extracted materials through dataset matching
        material_result = await self._match_materials(parsed, state)
        if material_result:
            return material_result

        # Determine next question or signal ready
        return self._next_question(state)

    def _is_finish_intent(self, text: str) -> bool:
        """Check if the user wants to finish the order."""
        text_lower = text.lower().strip()
        return any(re.search(p, text_lower) for p in FINISH_PHRASES)

    def _update_state(self, state: ConversationState, parsed: dict):
        """Update conversation state with Gemini-parsed data."""
        if parsed.get("customer_name") and not state.customer_name:
            state.customer_name = parsed["customer_name"]
            state.phase = "collecting"
            logger.info(f"Conversation: customer set to '{state.customer_name}'")

        if parsed.get("project_location") and not state.project_location:
            state.project_location = parsed["project_location"]
            logger.info(f"Conversation: location set to '{state.project_location}'")

        if state.customer_name and state.phase == "init":
            state.phase = "collecting"

    async def _match_materials(self, parsed: dict, state: ConversationState) -> dict | None:
        """Match Gemini-extracted materials against dataset using fuzzy matching."""
        items = parsed.get("items", [])
        if not items:
            return None

        # Deduplicate items from the same parse response
        seen = set()
        unique_items = []
        for item in items:
            key = (item.get("material_name", "").lower(), item.get("quantity"))
            if key not in seen:
                seen.add(key)
                unique_items.append(item)

        for item in unique_items:
            material_name = item.get("material_name", "")
            quantity = item.get("quantity")
            unit = item.get("unit", "each")
            extras = item.get("extras")

            if not material_name:
                continue

            # Add extras to state
            if extras and extras not in state.extras:
                state.extras.append(extras)

            # Fuzzy match against dataset
            match = dataset_matcher.match(material_name)

            if match and match.get("match_score", 0) >= 80:
                # High confidence — add directly
                if quantity:
                    state.items.append({
                        "material": match["item_name"],
                        "quantity": float(quantity),
                        "unit": match.get("unit", unit or "each"),
                        "matched_item": match,
                    })
                    state.phase = "collecting"
                    logger.info(f"Conversation: added {quantity} {match['item_name']}")
                else:
                    # Good match but no quantity — ask for it
                    matched_unit = match.get("unit", "each")
                    question = f"How many {matched_unit} of {match['item_name']} do you need?"
                    state.pending_confirmation = {
                        "type": "need_quantity",
                        "matched_item": match,
                        "input_text": material_name,
                    }
                    state.last_question = question
                    state.awaiting_field = "quantity"
                    return {
                        "response": question,
                        "state": state.to_dict(),
                        "action": "ask",
                        "suggestions": [],
                    }

            elif match and match.get("match_score", 0) >= 55:
                # Medium confidence — ask for confirmation
                suggestions = dataset_matcher.search(material_name, limit=3)
                state.pending_confirmation = {
                    "input_text": material_name,
                    "quantity": quantity,
                    "unit": unit,
                    "suggestions": suggestions,
                }
                suggestion_lines = "\n".join(
                    f"  {i+1}. {s['item_name']} (${s['total_price']:.2f}/{s.get('unit', 'each')})"
                    for i, s in enumerate(suggestions)
                )
                question = f'Did you mean one of these?\n{suggestion_lines}\nReply with the number.'
                state.last_question = question
                return {
                    "response": question,
                    "state": state.to_dict(),
                    "action": "confirm_match",
                    "suggestions": [s["item_name"] for s in suggestions],
                }
            else:
                # No match — show search results
                suggestions = dataset_matcher.search(material_name, limit=3)
                if suggestions:
                    state.pending_confirmation = {
                        "input_text": material_name,
                        "quantity": quantity,
                        "unit": unit,
                        "suggestions": suggestions,
                    }
                    suggestion_lines = "\n".join(
                        f"  {i+1}. {s['item_name']} (${s['total_price']:.2f}/{s.get('unit', 'each')})"
                        for i, s in enumerate(suggestions)
                    )
                    question = f'I couldn\'t find an exact match for "{material_name}". Did you mean:\n{suggestion_lines}\nReply with the number.'
                    state.last_question = question
                    return {
                        "response": question,
                        "state": state.to_dict(),
                        "action": "confirm_match",
                        "suggestions": [s["item_name"] for s in suggestions],
                    }

        return None

    async def _handle_confirmation(self, text: str, state: ConversationState) -> dict:
        """Handle user response to a fuzzy match confirmation or quantity request."""
        pending = state.pending_confirmation
        text_clean = text.strip()

        # Handle "need_quantity" type: user is providing a quantity
        if pending.get("type") == "need_quantity":
            # Use Gemini to parse the quantity from the response
            parsed = await gemini_parser.parse_followup(
                user_text=text_clean,
                question=state.last_question or "How many do you need?",
                state=state.to_dict(),
            )

            # Try to extract quantity from Gemini response
            qty = None
            for gitem in parsed.get("items", []):
                if gitem.get("quantity"):
                    qty = float(gitem["quantity"])
                    break

            # Fallback: extract number with regex
            if qty is None:
                qty_match = re.search(r"(\d+(?:\.\d+)?)", text_clean)
                if qty_match:
                    qty = float(qty_match.group(1))

            if qty:
                matched_item = pending["matched_item"]
                state.items.append({
                    "material": matched_item["item_name"],
                    "quantity": qty,
                    "unit": matched_item.get("unit", "each"),
                    "matched_item": matched_item,
                })
                state.pending_confirmation = None
                state.awaiting_field = None
                state.phase = "collecting"
                logger.info(f"Conversation: added {qty} {matched_item['item_name']}")
                return self._next_question(state)
            else:
                question = f"Please provide a number for the quantity of {pending['matched_item']['item_name']}."
                state.last_question = question
                return {
                    "response": question,
                    "state": state.to_dict(),
                    "action": "ask",
                    "suggestions": [],
                }

        suggestions = pending.get("suggestions", [])

        # Check if user replied with a number (1, 2, 3)
        num_match = re.match(r"^(\d)$", text_clean)
        if num_match:
            idx = int(num_match.group(1)) - 1
            if 0 <= idx < len(suggestions):
                selected = suggestions[idx]
                qty = pending.get("quantity")
                if qty:
                    state.items.append({
                        "material": selected["item_name"],
                        "quantity": float(qty),
                        "unit": selected.get("unit", pending.get("unit", "each")),
                        "matched_item": selected,
                    })
                    state.pending_confirmation = None
                    state.awaiting_field = None
                    state.phase = "collecting"
                    return self._next_question(state)
                else:
                    # Need quantity
                    matched_unit = selected.get("unit", "each")
                    question = f"How many {matched_unit} of {selected['item_name']} do you need?"
                    state.pending_confirmation = {
                        "type": "need_quantity",
                        "matched_item": selected,
                        "input_text": pending.get("input_text", ""),
                    }
                    state.last_question = question
                    state.awaiting_field = "quantity"
                    return {
                        "response": question,
                        "state": state.to_dict(),
                        "action": "ask",
                        "suggestions": [],
                    }

        # User typed a name — try to match
        match = dataset_matcher.match(text_clean)
        if match and match.get("match_score", 0) >= 70:
            qty = pending.get("quantity")
            if qty:
                state.items.append({
                    "material": match["item_name"],
                    "quantity": float(qty),
                    "unit": match.get("unit", pending.get("unit", "each")),
                    "matched_item": match,
                })
                state.pending_confirmation = None
                state.awaiting_field = None
                state.phase = "collecting"
                return self._next_question(state)
            else:
                matched_unit = match.get("unit", "each")
                question = f"How many {matched_unit} of {match['item_name']} do you need?"
                state.pending_confirmation = {
                    "type": "need_quantity",
                    "matched_item": match,
                    "input_text": text_clean,
                }
                state.last_question = question
                state.awaiting_field = "quantity"
                return {
                    "response": question,
                    "state": state.to_dict(),
                    "action": "ask",
                    "suggestions": [],
                }

        # Could not resolve
        state.pending_confirmation = None
        state.awaiting_field = None
        return {
            "response": "I didn't catch that. What material would you like to add?",
            "state": state.to_dict(),
            "action": "ask",
            "suggestions": [],
        }

    def _next_question(self, state: ConversationState) -> dict:
        """Determine the next question based on missing fields."""
        missing = state.missing_required()

        if "customer_name" in missing:
            question = "Who is this invoice for?"
            state.last_question = question
            state.awaiting_field = "customer_name"
            return {
                "response": question,
                "state": state.to_dict(),
                "action": "ask",
                "suggestions": [],
            }

        if "project_location" in missing:
            question = "What's the project location?"
            state.last_question = question
            state.awaiting_field = "project_location"
            return {
                "response": question,
                "state": state.to_dict(),
                "action": "ask",
                "suggestions": [],
            }

        if "material" in missing:
            question = "What materials do you need?"
            state.last_question = question
            state.awaiting_field = "material"
            return {
                "response": question,
                "state": state.to_dict(),
                "action": "ask",
                "suggestions": [],
            }

        # All required fields present
        state.awaiting_field = None
        state.last_question = None
        last_item = state.items[-1] if state.items else None
        item_summary = ""
        if last_item:
            item_summary = f'{int(last_item["quantity"])} {last_item["unit"]} of {last_item["material"]} added. '

        return {
            "response": f'{item_summary}Anything else, or say "done" to generate the invoice.',
            "state": state.to_dict(),
            "action": "ready",
            "suggestions": [],
        }

    async def _handle_finish(self, state: ConversationState, contractor_id: int, session_id: str) -> dict:
        """Handle finish intent — validate and return ready-to-create data."""
        missing = state.missing_required()
        if missing:
            field = missing[0]
            prompts = {
                "customer_name": "Who is this invoice for?",
                "project_location": "What's the project location?",
                "material": "You haven't added any materials yet. What do you need?",
            }
            question = prompts.get(field, "Please provide the missing information.")
            state.last_question = question
            state.awaiting_field = field
            return {
                "response": f"Before I generate the invoice: {question}",
                "state": state.to_dict(),
                "action": "ask",
                "suggestions": [],
            }

        # Build order summary
        items_text = "\n".join(
            f"  • {int(item['quantity'])} {item['unit']} {item['material']} — ${item['matched_item']['total_price'] * item['quantity']:.2f}"
            for item in state.items
        )
        extras_text = f"\n  Extras: {', '.join(state.extras)}" if state.extras else ""
        total = sum(item["matched_item"]["total_price"] * item["quantity"] for item in state.items)

        summary = (
            f"Order Summary:\n"
            f"  Customer: {state.customer_name}\n"
            f"  Location: {state.project_location}\n"
            f"  Items:\n{items_text}{extras_text}\n"
            f"  Estimated Total: ${total:.2f}\n\n"
            f"Generating invoice now..."
        )

        state.phase = "done"
        return {
            "response": summary,
            "state": state.to_dict(),
            "action": "create",
            "suggestions": [],
        }


# Global instance
conversation_manager = ConversationManager()
