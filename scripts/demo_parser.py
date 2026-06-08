import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.parsers.preference_parser import PreferenceParserTool

tool = PreferenceParserTool()

result = tool.invoke({"user_input": "Paris 5 days $3000"})

print(result)
