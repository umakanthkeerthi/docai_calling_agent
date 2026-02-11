
import asyncio
import os
import sys

# Ensure we can import modules from current directory
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from voice_server.agent.graph import agent_graph
from voice_server.booking_agent.graph import booking_graph

async def chat_session():
    print("==========================================")
    print("   DocAI Medical Agent - Terminal Mode    ")
    print("==========================================")
    print("Type 'exit', 'quit', or Press Ctrl+C to stop.")
    print("------------------------------------------")
    
    # Use a fixed thread ID to simulate a single continuous phone call
    config = {"configurable": {"thread_id": "cli_user_session_1"}}
    
    is_booking_active = False
    
    while True:
        try:
            # interactive input
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["exit", "quit"]:
                print("Ending session.")
                break
                
            print("Agent is thinking...", end="\r")
            
            # Prepare input state
            state_input = {"messages": [HumanMessage(content=user_input)]}
            
            if is_booking_active:
                # --- BOOKING MODE ---
                # Invoke booking agent directly
                booking_output = await booking_graph.ainvoke(state_input, config)
                
                final_response = booking_output.get("final_response")
                if final_response:
                    print(f"Agent (Booking): {final_response}")
                else:
                    messages = booking_output.get("messages", [])
                    if messages:
                         print(f"Agent (Booking): {messages[-1].content}")
                         
                # Check for completion
                if booking_output.get("booking_stage") == "complete":
                    print("\n[Booking Complete] Session Ended.")
                    break
            
            else:
                # --- CLINICAL MODE ---
                # Invoke clinical agent
                output = await agent_graph.ainvoke(state_input, config)
                
                # Check if we should trigger booking agent
                triage_decision = output.get("triage_decision", "PENDING")
                assessment_complete = output.get("assessment_complete", False)
                
                # Trigger booking if emergency or assessment complete
                should_book = (triage_decision == "EMERGENCY") or assessment_complete
                
                if should_book:
                    print("\n📅 [Booking Agent Activated]")
                    is_booking_active = True # SWITCH MODE
                    
                    medical_summary = output.get("final_advice", "Assessment complete.")
                    
                    # Initial invocation of booking agent
                    booking_output = await booking_graph.ainvoke(
                        {
                            "messages": [HumanMessage(content=user_input)], # Pass last input context
                            "triage_decision": triage_decision,
                            "medical_summary": medical_summary,
                            "booking_stage": "initial",
                            "doctor_name": "Dr. Smith"
                        },
                        config
                    )
                    
                    final_response = booking_output.get("final_response")
                    if final_response:
                        print(f"Agent (Booking): {final_response}")
                    else:
                        messages = booking_output.get("messages", [])
                        if messages:
                            print(f"Agent (Booking): {messages[-1].content}")
                else:
                    # Continue with clinical agent
                    final_response = output.get("final_response")
                    if final_response:
                        print(f"Agent: {final_response}")
                    else:
                        messages = output.get("messages", [])
                        if messages:
                            last_msg = messages[-1].content
                            print(f"Agent: {last_msg}")
            
            # Optional: Debug info
            # state = agent_graph.get_state(config).values
            # if state.get("triage_decision") == "EMERGENCY":
            #    print("[SYSTEM ALERT: EMERGENCY DETECTED]")
                
        except KeyboardInterrupt:
            print("\nSession interrupted.")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # Check keys
    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not found in .env")
        exit(1)
        
    try:
        asyncio.run(chat_session())
    except KeyboardInterrupt:
        pass
