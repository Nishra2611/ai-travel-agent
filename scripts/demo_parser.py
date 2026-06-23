# import sys
# from pathlib import Path

# sys.path.append(str(Path(__file__).resolve().parent.parent))
# from ai_travel_agent.parsers.preference_parser import PreferenceParserTool

# tool = PreferenceParserTool()

# result = tool.invoke({"user_input": "Paris 5 days $3000"})

# print(result)

"""
scripts/demo_parser.py — verify PreferenceParserTool with Ollama.
Run: poetry run python scripts/demo_parser.py
"""
from dotenv import load_dotenv

from ai_travel_agent.parsers.preference_parser import PreferenceParserTool

load_dotenv()

tool = PreferenceParserTool()
INPUTS = [
    "I want to visit Paris for 5 days in July under $3000",
    "2-week trip to Japan for 2 people, luxury, love food and culture",
    "Weekend in Goa, budget Rs 50000, adventure",
    "Romantic anniversary trip to Rome, 7 nights, mid-range budget",
]

print("=" * 58)
print("PreferenceParserTool — Ollama demo")
print("=" * 58)
for inp in INPUTS:
    print(f"\nInput : {inp}")
    result = tool._run(user_input=inp)
    print(f"  destination  : {result.get('destination')}")
    print(f"  duration_days: {result.get('duration_days')}")
    print(f"  budget_usd   : {result.get('budget_usd')}")
    print(f"  travel_style : {result.get('travel_style')}")
    print(f"  confidence   : {result.get('confidence_score')}")

print("\n✓ Parser demo complete\n")
