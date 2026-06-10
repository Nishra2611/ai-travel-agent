from src.tools.dummy_tool import DummyFlightTool

tool = DummyFlightTool()

print("First run (fetches from API):")
result = tool._run(origin="AMD", destination="DEL")
print(result)

print("\nSecond run (should come from cache):")
result2 = tool._run(origin="AMD", destination="DEL")
print(result2)
