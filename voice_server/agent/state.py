
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class PatientProfile(TypedDict):
    age: Optional[int]
    gender: Optional[str]
    symptoms: List[str]
    denied_symptoms: List[str]
    duration: Optional[str]
    medical_history: List[str]
    current_meds: List[str]

class TriageState(TypedDict):
    # Standard LangGraph message history
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Patient Data
    patient_profile: PatientProfile
    
    # Agent Reasoning State
    retrieved_protocols: List[str] # Raw text chunks
    differential_diagnosis: List[str] # Hypotheses
    safety_checklist: List[str] # The "Plan"
    investigated_symptoms: List[str] # Memory of what has been asked
    
    # Decisions
    triage_decision: str # "PENDING", "EMERGENCY", "COMPLETE"
    final_advice: str
    final_response: str # The actual message sent to the user
    
    # Flags
    assessment_complete: bool # True when strategist finishes summary
    
    # Meta
    session_id: str
