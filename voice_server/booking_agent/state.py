
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class BookingState(TypedDict):
    # Message history
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Context from Clinical Agent
    triage_decision: str  # "EMERGENCY" or "ROUTINE"
    medical_summary: str  # Summary from clinical assessment
    
    # Booking flow state
    booking_stage: str  # 'emergency_ask', 'date_ask', 'slot_ask', 'confirmed', 'complete'
    
    # Booking details
    selected_date: Optional[str]
    selected_time: Optional[str]
    doctor_name: str  # Mock: "Dr. Smith"
    
    # Final response
    final_response: str
