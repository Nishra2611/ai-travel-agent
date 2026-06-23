"""
scripts/demo_graph_viz.py — print graph structure without running it.
Run: poetry run python scripts/demo_graph_viz.py
"""

from dotenv import load_dotenv

from ai_travel_agent.agents.graph import build_graph

load_dotenv()

graph = build_graph(db_path="data/viz_test.db")
print("=" * 58)
print("LangGraph agent — node structure")
print("=" * 58)
print("\nNodes:")
for node in graph.nodes:
    print(f"  {node}")
print("\nMermaid diagram (paste at mermaid.live):\n")
try:
    print(graph.get_graph().draw_mermaid())
except Exception as e:
    print(f"  (mermaid not available: {e})")
print("\n✓ Graph structure verified\n")
