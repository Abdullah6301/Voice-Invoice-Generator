"""
Invoice Generator Dataset Matching Engine
Fuzzy matches extracted material text against the master dataset.
"""

from rapidfuzz import fuzz, process
from loguru import logger


class DatasetMatcher:
    """
    Matches extracted material names against the construction dataset
    using fuzzy string matching.
    """

    def __init__(self):
        self.dataset_items = []
        self.item_names = []
        self._loaded = False
        logger.info("Dataset matcher initialized")

    async def load_dataset(self, db_manager):
        """Load dataset items from database for matching."""
        try:
            items = await db_manager.fetch_all(
                "SELECT * FROM dataset_items ORDER BY item_name"
            )
            self.dataset_items = items
            self.item_names = [item["item_name"] for item in items]
            self._loaded = True
            logger.info(f"Dataset matcher loaded {len(items)} items")
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")

    def match(self, material_text: str, threshold: int = 55) -> dict | None:
        """
        Find the best matching dataset item for a material description.

        Args:
            material_text: Extracted material text from NER
            threshold: Minimum fuzzy match score (0-100)

        Returns:
            Best matching dataset item dict with 'score', or None
        """
        if not self._loaded or not self.item_names:
            logger.warning("Dataset not loaded, cannot match")
            return None

        if not material_text or not material_text.strip():
            return None

        # Clean input
        clean_text = material_text.strip().lower()

        # Try exact match first
        for item in self.dataset_items:
            if item["item_name"].lower() == clean_text:
                result = dict(item)
                result["match_score"] = 100
                logger.info(f"Exact match: '{material_text}' -> '{item['item_name']}' (100)")
                return result

        # Fuzzy match using token_sort_ratio for best results with reworded phrases
        best_match = process.extractOne(
            clean_text,
            self.item_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )

        if best_match:
            matched_name, score, idx = best_match
            result = dict(self.dataset_items[idx])
            result["match_score"] = score
            logger.info(f"Fuzzy match: '{material_text}' -> '{matched_name}' (score: {score})")
            return result

        # Try partial ratio as fallback
        best_match = process.extractOne(
            clean_text,
            self.item_names,
            scorer=fuzz.partial_ratio,
            score_cutoff=threshold + 10,
        )

        if best_match:
            matched_name, score, idx = best_match
            result = dict(self.dataset_items[idx])
            result["match_score"] = score
            logger.info(f"Partial match: '{material_text}' -> '{matched_name}' (score: {score})")
            return result

        logger.warning(f"No match found for: '{material_text}'")
        return None

    def match_multiple(self, material_texts: list[str], threshold: int = 55) -> list[dict]:
        """
        Match multiple material texts against the dataset.

        Args:
            material_texts: List of material description strings
            threshold: Minimum fuzzy match score

        Returns:
            List of match results (including unmatched items)
        """
        results = []
        for text in material_texts:
            match = self.match(text, threshold)
            if match:
                results.append({
                    "input_text": text,
                    "matched": True,
                    "dataset_item": match,
                })
            else:
                results.append({
                    "input_text": text,
                    "matched": False,
                    "dataset_item": None,
                })
        return results

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search dataset items by partial match.

        Args:
            query: Search query text
            limit: Maximum results to return

        Returns:
            List of matching dataset items with scores
        """
        if not self._loaded or not query:
            return []

        results = process.extract(
            query.lower(),
            self.item_names,
            scorer=fuzz.token_sort_ratio,
            limit=limit,
        )

        matched = []
        for name, score, idx in results:
            if score >= 40:
                item = dict(self.dataset_items[idx])
                item["match_score"] = score
                matched.append(item)

        return matched


# Global matcher instance
dataset_matcher = DatasetMatcher()
