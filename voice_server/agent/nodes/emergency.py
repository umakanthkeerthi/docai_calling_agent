
from typing import Dict, Any
import json
import os
from langchain_groq import ChatGroq
from voice_server.core.config import settings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

llm_scanner = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0
)

async def emergency_scan_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        messages = state.get("messages", [])
        if not messages:
            return {"triage_decision": "PENDING"} 
            
        last_user_msg = messages[-1].content
        
        # Load Rules (Simplified Path)
        emergency_rules = []
        # ... logic to load rules ...

        prompt = f"""
        You are EMERGENCY TRIAGE.
        User Input: "{last_user_msg}"
        Detect Life Threatening conditions.
        OUTPUT JSON: {{ "is_emergency": bool, "reason": "str", "final_response": "str(optional)" }}
        """
        
        response = await llm_scanner.ainvoke([
            SystemMessage(content="You are a strict JSON output bot."),
            HumanMessage(content=prompt)
        ])
        
        result_str = response.content.replace("```json", "").replace("```", "").strip()
        result = json.loads(result_str)

        
        if result.get("is_emergency"):
            # Set emergency flag but don't end call
            # Booking agent will handle the emergency flow
            return {
                "triage_decision": "EMERGENCY",
                "final_response": "",  # Booking agent will provide response
                "messages": []  # Booking agent will handle messaging
            }
        
        return {"triage_decision": "ROUTINE"}
        
    except Exception as e:
        print(f"Emerg Error: {e}")
        return {"triage_decision": "ROUTINE"}
