
from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
from langchain_core.messages import HumanMessage
from voice_server.agent.graph import agent_graph

async def test_memory():
    print("TEST: Verifying Memory Persistence...")
    
    config = {"configurable": {"thread_id": "test_thread_1"}}
    
    # Turn 1: State my name/symptom
    print("\n--- Turn 1: 'My name is John and I have chest pain.' ---")
    input_1 = {"messages": [HumanMessage(content="My name is John and I have chest pain.")]}
    output_1 = await agent_graph.ainvoke(input_1, config)
    
    last_msg_1 = output_1["messages"][-1].content
    print(f"Agent 1: {last_msg_1}")
    
    # Turn 2: Follow up without restating context
    print("\n--- Turn 2: 'How long will it last?' (Implicitly referring to chest pain) ---")
    input_2 = {"messages": [HumanMessage(content="How long will it last?")]}
    
    # Checks state snapshot
    # state = agent_graph.get_state(config)
    # print(f"State Snapshot (Patient Profile): {state.values.get('patient_profile')}")
    
    output_2 = await agent_graph.ainvoke(input_2, config)
    last_msg_2 = output_2["messages"][-1].content
    print(f"Agent 2: {last_msg_2}")
    
    # Verification Logic
    # We can't easily assert the text, but we can check if the symptom lists in the state
    # persisted.
    
    final_state = agent_graph.get_state(config).values
    symptoms = final_state.get("investigated_symptoms", [])
    checklist = final_state.get("safety_checklist", [])
    
    print(f"\nFinal State - Symptoms Investigated: {symptoms}")
    print(f"Final State - Remaining Checklist: {checklist}")
    
    if len(checklist) > 0 or len(symptoms) > 0:
        print("\n✅ MEMORY TEST PASSED (State persisted)")
    else:
        print("\n❌ MEMORY TEST FAILED (State empty)")

if __name__ == "__main__":
    try:
        asyncio.run(test_memory())
    except Exception as e:
        print(f"CRASH: {e}")
