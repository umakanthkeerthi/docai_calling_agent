
from typing import Dict, Any
from langchain_core.messages import AIMessage, HumanMessage
from langchain_groq import ChatGroq
from voice_server.core.config import settings

# LLM for understanding user responses
llm_booking = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0.0
)

# Mock data
DOCTOR_NAME = "Dr. Smith"
AVAILABLE_SLOTS = ["9 AM", "10 AM", "3 PM"]

def scheduler_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handles appointment booking flow.
    Two modes: Emergency and Standard.
    """
    messages = state.get("messages", [])
    triage_decision = state.get("triage_decision", "ROUTINE")
    booking_stage = state.get("booking_stage", "initial")
    
    # Initialize doctor name
    if not state.get("doctor_name"):
        state["doctor_name"] = DOCTOR_NAME
        
    print(f"DEBUG: Scheduler Node - Stage: {booking_stage}, Last Msg: '{messages[-1].content if messages else ''}'")
    
    # EMERGENCY FLOW
    if triage_decision == "EMERGENCY":
        if booking_stage == "initial":
            response = (
                "⚠️ Your symptoms indicate you need immediate medical attention. "
                "If you feel worse, please call 108 for an ambulance right away. "
                "Would you like me to arrange an urgent consultation with a doctor?"
            )
            return {
                "booking_stage": "emergency_ask",
                "final_response": response,
                "messages": [AIMessage(content=response)]
            }
        
        elif booking_stage == "emergency_ask":
            # Check user response
            last_msg = messages[-1].content.lower() if messages else ""
            
            if "yes" in last_msg or "sure" in last_msg or "okay" in last_msg:
                response = (
                    f"I've found {DOCTOR_NAME} near you. "
                    "Please consult them within the next hour. "
                    "You will receive the clinic address via SMS. Take care!"
                )
                return {
                    "booking_stage": "complete",
                    "final_response": response,
                    "messages": [AIMessage(content=response)]
                }
            else:
                response = "Understood. Please take care and call 108 if needed. Goodbye."
                return {
                    "booking_stage": "complete",
                    "final_response": response,
                    "messages": [AIMessage(content=response)]
                }
    
    # STANDARD BOOKING FLOW
    else:
        if booking_stage == "initial":
            # Step 1: Ask if they want to book (Explicit confirmation request)
            response = (
                f"Your assessment is complete. I've found {DOCTOR_NAME} near you. "
                "Do you want to book an appointment?"
            )
            return {
                "booking_stage": "booking_ask",
                "final_response": response,
                "messages": [AIMessage(content=response)]
            }
        
        elif booking_stage == "booking_ask":
            # Step 2: Check Yes/No
            last_msg = messages[-1].content.lower() if messages else ""
            if "yes" in last_msg or "sure" in last_msg or "book" in last_msg:
                response = "Okay. When do you have to book the appointment? Please tell me the date."
                return {
                    "booking_stage": "date_ask",
                    "final_response": response,
                    "messages": [AIMessage(content=response)]
                }
            else:
                response = "Okay. You can book later if you wish. Thank you for calling. Goodbye."
                return {
                    "booking_stage": "complete",
                    "final_response": response,
                    "messages": [AIMessage(content=response)]
                }

        elif booking_stage == "date_ask":
            # Step 3: Got Date -> Show Slots
            last_msg = messages[-1].content if messages else ""
            selected_date = last_msg
            
            slots_str = ", ".join(AVAILABLE_SLOTS)
            response = (
                f"I have found available slots at {slots_str}. "
                "Which slot do you want to book?"
            )
            return {
                "booking_stage": "slot_ask",
                "selected_date": selected_date,
                "final_response": response,
                "messages": [AIMessage(content=response)]
            }
        
        elif booking_stage == "slot_ask":
            # Step 4: Got Slot -> Confirm
            last_msg = messages[-1].content if messages else ""
            selected_time = last_msg
            selected_date = state.get("selected_date", "the requested date")
            
            response = (
                f"Your slot at {selected_time} on {selected_date} is confirmed. "
                "You will receive further information through a call. Goodbye!"
            )
            return {
                "booking_stage": "complete",
                "selected_time": selected_time,
                "final_response": response,
                "messages": [AIMessage(content=response)]
            }
    
    # Fallback
    return {
        "final_response": "Thank you for calling. Goodbye!",
        "booking_stage": "complete"
    }
