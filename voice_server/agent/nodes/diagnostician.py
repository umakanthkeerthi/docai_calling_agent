
from typing import Dict, Any
from voice_server.core.config import settings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import difflib

# Using OpenAI Client for GPT-OSS-120b (as per original successful config)
from groq import AsyncGroq
client = AsyncGroq(api_key=settings.GROQ_API_KEY)

async def simple_invoke(prompt):
    completion = await client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )
    return completion.choices[0].message.content


def is_similar(a, b, threshold=0.6):
    """Check if strings are similar using SequenceMatcher"""
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() > threshold

async def diagnostician_node(state: Dict[str, Any]) -> Dict[str, Any]:

    messages = state.get("messages", [])
    protocols = state.get("retrieved_protocols", [])
    current_checklist = state.get("safety_checklist", [])
    
    # Context
    history_list = [f"{m.type}: {m.content}" for m in messages[-20:]]
    history_str = "\n".join(history_list)
    knowledge = "\n\n".join(protocols)
    
    # Gather Investigated Symptoms (Known persistence)
    investigated = state.get("investigated_symptoms", [])
    
    # --- QUESTION LIMIT CHECK ---
    # If we have asked more than 6 questions, force wrap up.
    if len(investigated) > 6:
        print("DEBUG: Max questions reached. Forcing completion.")
        return {
            "triage_decision": "COMPLETE",
            "safety_checklist": [], # Clear pending to force Strategist to summarize
            "differential_diagnosis": state.get("differential_diagnosis", [])
        }
    
    # Helper to clean duplicate against history + investigated
    def clean_duplicates(questions, forbidden_list_):
        cleaned = []
        for q in questions:
            if not q or len(q) < 5: continue
            
            is_dup = False
            # 1. Exact/Fuzzy Match against forbidden
            for forbidden in forbidden_list_:
                if is_similar(q, forbidden):
                    is_dup = True
                    break
            
            # 2. Check internal dup in cleaned list
            if not is_dup:
                for existing in cleaned:
                    if is_similar(q, existing):
                        is_dup = True
                        break
            
            if not is_dup:
                cleaned.append(q)
        return cleaned

    # Gather History for prohibition
    message_history_texts = [m.content for m in messages if m.type == 'ai']
    forbidden_list = investigated + message_history_texts

    if not current_checklist:
        # INITIAL MODE
        prompt = f"""
        You are an Expert Diagnostic AI.
        PATIENT HISTORY: {history_str}
        KNOWLEDGE: {knowledge}
        TASK: Create FOCUSED assessment plan (Max 4 questions).
        OUTPUT JSON:
        {{ "differential_diagnosis": ["Str 1"], "new_questions": ["Q1", "Q2"] }}
        """
        try:
            import json
            result_str = await simple_invoke(prompt)

            result = json.loads(result_str.replace("```json", "").replace("```", "").strip())
            new_questions = result.get("new_questions", [])
            
            # Robust Initial Deduplication
            final_checklist = clean_duplicates(new_questions, forbidden_list)
            
            return {
                "differential_diagnosis": result.get("differential_diagnosis", []),
                "safety_checklist": final_checklist,
                "triage_decision": "PENDING"
            }
        except Exception as e:
            print(f"Error in Initial Diag: {e}")
            return {}
    else:
        # FOLLOW-UP MODE
        just_asked = current_checklist[0]
        remaining_checklist = current_checklist[1:]
        
        # --- AGGRESSIVE PRUNING OF REMAINING CHECKLIST ---
        # Before adding new questions, ensure remaining ones aren't already answered/asked
        # This handles cases where a duplicate slipped in or was asked out-of-order
        pruned_remaining = clean_duplicates(remaining_checklist, forbidden_list)
        
        prompt = f"""
        HISTORY: {history_str}
        PENDING: {pruned_remaining}
        LAST QUESTION: "{just_asked}"
        TASK: Do you need critical questions?
        OUTPUT JSON: {{ "differential_diagnosis": [], "new_questions_to_add": [], "stop_asking": bool }}
        """
        try:
            import json
            result_str = await simple_invoke(prompt)

            result = json.loads(result_str.replace("```json", "").replace("```", "").strip())
            
            new_additions = result.get("new_questions_to_add", [])
            
            # Dedup new additions against History + Pruned Remaining
            full_forbidden = forbidden_list + pruned_remaining
            cleaned_new_questions = clean_duplicates(new_additions, full_forbidden)
            
            updated_checklist = pruned_remaining + cleaned_new_questions
            status = "COMPLETE" if (result.get("stop_asking") or not updated_checklist) else "PENDING"
            
            if status == "COMPLETE": updated_checklist = []
            
            return {
                "differential_diagnosis": result.get("differential_diagnosis", []),
                "safety_checklist": updated_checklist,
                "triage_decision": status 
            }
        except Exception as e:
             print(f"Error in Follow-up Diag: {e}")
             return {"safety_checklist": remaining_checklist}
