"""Quick test of the AI pipeline."""
import asyncio
import sys
sys.path.insert(0, '.')

from ai_engine.intent_recognition import intent_recognizer
from ai_engine.ner_engine import ner_engine
from ai_engine.dataset_matcher import dataset_matcher
from database.connection import db_manager


async def test():
    # Load dataset
    await dataset_matcher.load_dataset(db_manager)

    # Test with the PRD example command
    text = "Create an invoice for Mike Miller at West Oak Site. Add 100 feet of horizontal cedar fencing with smart lock gate and solid stain."
    
    print("=" * 60)
    print(f"Input: {text}")
    print("=" * 60)

    # Intent
    intent = intent_recognizer.recognize(text)
    print(f"\nIntent: {intent['intent']} (confidence: {intent['confidence']})")

    # NER
    entities = ner_engine.extract_entities(text)
    print(f"Customer: {entities['customer_name']}")
    print(f"Location: {entities['location']}")
    print(f"Materials: {entities['materials']}")
    print(f"Quantities: {entities['quantities']}")
    print(f"Features: {entities['features']}")

    # Dataset Matching
    print("\nDataset Matches:")
    for mat in entities['materials']:
        match = dataset_matcher.match(mat)
        if match:
            print(f"  '{mat}' -> '{match['item_name']}' (score: {match['match_score']}, price: ${match['total_price']})")
        else:
            print(f"  '{mat}' -> NO MATCH")

    # Test more intents
    print("\n--- Intent Tests ---")
    tests = [
        "Add 50 feet cedar fencing",
        "Remove the drywall sheets",
        "Finalize the invoice",
        "Save as draft",
    ]
    for t in tests:
        r = intent_recognizer.recognize(t)
        print(f"  '{t}' -> {r['intent']} ({r['confidence']})")


if __name__ == "__main__":
    asyncio.run(test())
