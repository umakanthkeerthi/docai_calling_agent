
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Verify keys
if not os.getenv("GROQ_API_KEY"):
    print("SKIPPING GRAPH TEST: GROQ_API_KEY not found.")
    exit(0)

try:
    print("Importing agent graph...")
    from voice_server.agent.graph import agent_graph
    print("Graph imported successfully.")
    
    # Optional: Invoke with routine input
    from langchain_core.messages import HumanMessage
    input_state = {"messages": [HumanMessage(content="I have a headache.")]}
    print("Invoking graph with test input...")
    # This might require API calls, so it could fail if keys are invalid or quota exceeded.
    # We'll wrap in try/except.
    
    # We use asyncio run for async graph
    async def test():
         config = {"configurable": {"thread_id": "verify_graph_test"}}
         result = await agent_graph.ainvoke(input_state, config=config)
         print("Graph invocation result:", result)
         
    asyncio.run(test())
    print("Graph test PASSED.")

except Exception as e:
    print(f"GRAPH TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
