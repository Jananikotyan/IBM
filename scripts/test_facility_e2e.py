ce import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import logging
logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, '.')
from app.agent.mock_agent import MockSehatAgent

agent = MockSehatAgent()
queries = [
    "find nearest hospital near mangalore",
    "nearest hospital in bangalore",
    "hospital near 575001",
    "find phc near delhi",
]
print("=== Facility Query End-to-End Test ===\n")
for q in queries:
    print(f'Query: "{q}"')
    result = agent.chat(q, session_id="facility-test")
    resp = result.get("response", "")
    status = "PASS" if len(resp) > 30 else "FAIL"
    print(f"Status : [{status}]")
    print(f"Preview: {resp[:150].strip()}")
    print()
