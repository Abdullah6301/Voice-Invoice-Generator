"""
Invoice Generator Named Entity Recognition (NER) Engine
Extracts construction-specific entities from text using spaCy + custom rules.
"""

import re
import spacy
from loguru import logger


# Construction-specific material keywords for entity matching
MATERIAL_KEYWORDS = [
    "cedar", "fence", "fencing", "panel", "picket", "post", "rail",
    "wood", "stud", "plywood", "lumber", "deck", "board", "beam",
    "concrete", "mix", "block", "rebar", "steel", "wire", "mesh",
    "anchor", "bolt", "slab", "paver",
    "drywall", "sheet", "joint", "compound", "tape", "screw", "corner", "bead",
    "brick", "masonry", "mortar", "stone", "veneer", "retaining",
    "pipe", "pvc", "copper", "faucet", "toilet", "sink", "shower",
    "drain", "sump", "pump", "water", "heater", "plumbing",
    "conduit", "wire", "electrical", "panel", "outlet", "switch",
    "gfci", "circuit", "breaker", "junction", "box", "recessed", "light",
    "ceiling", "fan", "led",
    "shingle", "roof", "roofing", "underlayment", "ridge", "vent",
    "flashing", "drip", "edge", "gutter", "skylight", "metal",
    "insulation", "fiberglass", "batt", "spray", "foam", "rigid", "vapor",
    "tile", "ceramic", "porcelain", "vinyl", "plank", "flooring",
    "carpet", "grout", "adhesive",
    "paint", "primer", "stain", "caulk", "roller",
    "hvac", "duct", "ductwork", "thermostat", "register", "filter",
    "gate", "lock", "smart", "chain", "link", "wrought", "iron",
    "scaffolding", "dumpster",
    "horizontal", "vertical", "privacy",
]

# Unit patterns
UNIT_PATTERNS = [
    (r"\b(linear\s+feet|linear\s+ft|lin\.?\s*ft)\b", "linear_ft"),
    (r"\b(square\s+feet|square\s+ft|sq\.?\s*ft|sqft)\b", "sq_ft"),
    (r"\b(cubic\s+yards?|cubic\s+yd)\b", "cubic_yd"),
    (r"\b(feet|foot|ft)\b", "linear_ft"),
    (r"\b(each|ea|piece|pieces|pcs|unit|units)\b", "each"),
    (r"\b(gallon|gallons|gal)\b", "gallon"),
    (r"\b(roll|rolls)\b", "each"),
    (r"\b(bag|bags)\b", "each"),
    (r"\b(box|boxes)\b", "each"),
    (r"\b(sheet|sheets)\b", "each"),
    (r"\b(bundle|bundles)\b", "each"),
    (r"\b(hour|hours|hr|hrs)\b", "hour"),
    (r"\b(day|days)\b", "day"),
]


class NEREngine:
    """
    Named Entity Recognition for construction voice commands.
    Extracts: customer_name, location, material, quantity, unit, features
    """

    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy NER model loaded (en_core_web_sm)")
        except OSError:
            logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
            self.nlp = None

    def extract_entities(self, text: str) -> dict:
        """
        Extract all relevant entities from a voice command.

        Args:
            text: Transcribed text input

        Returns:
            Dictionary with extracted entities
        """
        if not text:
            return self._empty_entities()

        entities = {
            "customer_name": None,
            "location": None,
            "materials": [],
            "quantities": [],
            "features": [],
            "raw_text": text,
        }

        # Use spaCy for PERSON and GPE/LOC extraction
        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ == "PERSON" and not entities["customer_name"]:
                    entities["customer_name"] = ent.text
                elif ent.label_ in ("GPE", "LOC", "FAC"):
                    if not entities["location"]:
                        entities["location"] = ent.text

        # Extract customer name from "for [Name]" pattern
        if not entities["customer_name"]:
            name_match = re.search(
                r"\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                text
            )
            if name_match:
                entities["customer_name"] = name_match.group(1)

        # Extract location from "at [Location]" pattern
        if not entities["location"]:
            loc_match = re.search(
                r"\bat\s+(.+?)(?:\.|,|\bAdd\b|\badd\b|$)",
                text
            )
            if loc_match:
                location = loc_match.group(1).strip()
                # Clean up: remove trailing material-related words
                location = re.sub(
                    r"\s+(?:add|include|with|and\s+\d).*$",
                    "",
                    location,
                    flags=re.IGNORECASE,
                ).strip()
                if location and len(location) > 2:
                    entities["location"] = location

        # Extract quantities and materials
        qty_material_patterns = [
            # "100 feet of horizontal cedar fencing"
            r"(\d+(?:\.\d+)?)\s*(linear\s+feet|linear\s+ft|square\s+feet|square\s+ft|cubic\s+yards?|feet|foot|ft|gallons?|gal|bags?|boxes?|sheets?|bundles?|rolls?|pieces?|pcs|units?|each|hours?|hr|days?|sqft|sq\s*ft)\s+(?:of\s+)?(.+?)(?:\bwith\b|\band\b|\bat\b|,|$)",
            # "100 cedar fence panels"
            r"(\d+(?:\.\d+)?)\s+(.+?)(?:\s+(?:at|with|and|for)\b|,|$)",
        ]

        text_lower = text.lower()
        found_materials = set()

        for pattern in qty_material_patterns:
            for match in re.finditer(pattern, text_lower):
                groups = match.groups()
                if len(groups) == 3:
                    qty = float(groups[0])
                    unit = self._normalize_unit(groups[1])
                    material_text = groups[2].strip()
                elif len(groups) == 2:
                    qty = float(groups[0])
                    material_text = groups[1].strip()
                    unit = self._detect_unit(material_text)
                    # Remove unit words from material text
                    for upattern, _ in UNIT_PATTERNS:
                        material_text = re.sub(upattern, "", material_text, flags=re.IGNORECASE).strip()
                else:
                    continue

                # Clean material text
                material_text = self._clean_material_text(material_text)

                if material_text and material_text not in found_materials:
                    found_materials.add(material_text)
                    entities["quantities"].append({
                        "value": qty,
                        "unit": unit,
                        "material_text": material_text,
                    })
                    entities["materials"].append(material_text)

        # Extract features (e.g., "smart lock gate", "solid stain")
        feature_patterns = [
            r"\bwith\s+(.+?)(?:\band\b|,|$)",
            r"\bincluding\s+(.+?)(?:\band\b|,|$)",
        ]
        for pattern in feature_patterns:
            for match in re.finditer(pattern, text_lower):
                feature = match.group(1).strip()
                if feature and len(feature) > 2:
                    # Check if this is actually a material/quantity
                    if not re.match(r"^\d+", feature):
                        entities["features"].append(feature)
                    else:
                        # Parse as additional quantity+material
                        sub_match = re.match(
                            r"(\d+(?:\.\d+)?)\s*(.+)",
                            feature,
                        )
                        if sub_match:
                            qty = float(sub_match.group(1))
                            mat = self._clean_material_text(sub_match.group(2))
                            unit = self._detect_unit(mat)
                            if mat and mat not in found_materials:
                                found_materials.add(mat)
                                entities["quantities"].append({
                                    "value": qty,
                                    "unit": unit,
                                    "material_text": mat,
                                })
                                entities["materials"].append(mat)

        logger.info(f"NER extracted: customer='{entities['customer_name']}', "
                    f"location='{entities['location']}', "
                    f"materials={entities['materials']}, "
                    f"quantities={len(entities['quantities'])}")

        return entities

    def _normalize_unit(self, unit_text: str) -> str:
        """Normalize unit text to standard abbreviation."""
        unit_text = unit_text.lower().strip()
        for pattern, normalized in UNIT_PATTERNS:
            if re.search(pattern, unit_text, re.IGNORECASE):
                return normalized
        return "each"

    def _detect_unit(self, text: str) -> str:
        """Detect unit from material text."""
        text_lower = text.lower()
        for pattern, normalized in UNIT_PATTERNS:
            if re.search(pattern, text_lower):
                return normalized
        return "each"

    def _clean_material_text(self, text: str) -> str:
        """Clean and normalize material text."""
        # Remove common noise words
        noise = ["the", "a", "an", "some", "of", "and", "or", "please", "also"]
        words = text.split()
        cleaned = [w for w in words if w.lower() not in noise]
        result = " ".join(cleaned).strip()
        # Remove trailing punctuation
        result = re.sub(r"[.,;:!?]+$", "", result)
        return result

    def _empty_entities(self) -> dict:
        """Return empty entities structure."""
        return {
            "customer_name": None,
            "location": None,
            "materials": [],
            "quantities": [],
            "features": [],
            "raw_text": "",
        }


# Global NER instance
ner_engine = NEREngine()
