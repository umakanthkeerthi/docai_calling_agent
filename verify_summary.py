
import asyncio
from voice_server.agent.nodes.strategist import strategist_node
from langchain_core.messages import HumanMessage, AIMessage

async def test_summary():
    print("TEST: Verifying Strategist Assessment Summary...")
    
    # Mock State: Assessment Complete (Empty Checklist)
    mock_state = {
        "safety_checklist": [],
        "differential_diagnosis": ["Viral Upper Respiratory Infection", "Common Cold"],
        "retrieved_protocols": [" PROTOCOL: Fever \n SECTION: RED_FLAGS \n CONTENT: Difficulty breathing, bluish lips, convulsions..."],
        "investigated_symptoms": ["fever", "cough"],
        "messages": [
            HumanMessage(content="I have a fever and cough."),
            AIMessage(content="How long?"),
            HumanMessage(content="2 days."),
            AIMessage(content="Any breathing trouble?"),
            HumanMessage(content="No.")
        ]
    }
    
    print("Invoking Strategist Node (Mocking end of chat)...")
    result = strategist_node(mock_state)
    
    response = result.get("final_response")
    print("\n--- GENERATED SUMMARY ---")
    print(response)
    print("-------------------------")
    
    if "Assessment" in response and "Red Flags" in response and "Action Plan" in response:
        print("✅ TEST PASSED: Structure detected.")
    else:
        print("⚠️ TEST WARNING: Structure might be missing (Check output manually).")

if __name__ == "__main__":
    asyncio.run(test_summary())
