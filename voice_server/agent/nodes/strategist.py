
from typing import Dict, Any
from voice_server.core.config import settings
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

# Initialize LLM for Strategist (Using the same model as others or a specific one)
# Llama-3.3-70b is good for summarization
# Initialize LLM for Strategist (Summarization needs high quality)
llm_strategist = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.2
)

# Initialize Fast LLM for Intent Classification (User preference: gpt-oss-120b)
llm_fast = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=settings.GROQ_API_KEY,
    temperature=0.0
)

async def strategist_node(state: Dict[str, Any]) -> Dict[str, Any]:

    checklist = state.get("safety_checklist", [])
    diagnosis = state.get("differential_diagnosis", [])
    protocols = state.get("retrieved_protocols", [])
    messages = state.get("messages", [])
    
    if not checklist:
        # Assessment complete - generate detailed summary using LLM
        
        # 1. Prepare Context
        history_list = [f"{m.type}: {m.content}" for m in messages[-20:]]
        history_str = "\n".join(history_list)
        diagnosis_str = ", ".join(diagnosis) if diagnosis else "Undetermined routine condition"
        knowledge_str = "\n\n".join(protocols)
        
        prompt = f"""
        You are a Senior Medical Triage Agent. You have just completed an assessment.
        
        PATIENT HISTORY:
        {history_str}
        
        LIKELY CONDITIONS Identified:
        {diagnosis_str}
        
        MEDICAL KNOWLEDGE (Guidelines):
        {knowledge_str}
        
        TASK:
        Generate a Compassionate and Structured Final Assessment Summary for the patient.
        
        FORMAT (Strictly follow this structure):
        
        1. **Assessment**:
           [Explain clearly what the symptoms suggest in simple terms. E.g. "Your symptoms of X and Y suggest a likely viral infection..."]
           
        2. **Red Flags (Warning Signs)**:
           [List 3 distinct danger signs relevant to this condition. Use bullet points.]
           - If you experience [Symptom A]
           - If [Symptom B] occurs
           
        3. **Action Plan (Recommendation)**:
           [Clear advice on when to see a doctor. E.g. "Monitor at home for 24 hours," or "See a doctor immediately if..."]
           
        TONE: Professional, Empathetic, Clear, Non-Alarmist (unless emergency).
        """
        
        try:
            response = await llm_strategist.ainvoke(prompt)

            final_text = response.content.strip()
            
            return {
                "triage_decision": "COMPLETE", 
                "final_response": final_text,
                "messages": [AIMessage(content=final_text)],
                "assessment_complete": True # Signal for booking agent
            }
            
        except Exception as e:
            print(f"Error generating summary: {e}")
            fallback_text = f"Assessment Complete. Possible conditions: {diagnosis_str}. Please consult a doctor if symptoms worsen."
            return {
                "triage_decision": "COMPLETE", 
                "final_response": fallback_text,
                "messages": [AIMessage(content=fallback_text)],
                "assessment_complete": True
            }
    
    # --- SMART STRATEGIST LOGIC ---
    
    # 1. Get the last user message to understand context
    last_user_msg = None
    for m in reversed(messages):
        if m.type == 'human':
            last_user_msg = m.content
            break
            
    # If no user message (start of convo), just start checklist
    if not last_user_msg:
        next_task = checklist[0] if checklist else "How can I help you regarding your health?"
        return {
            "final_response": next_task,
            "investigated_symptoms": state.get("investigated_symptoms", []) + [next_task],
            "messages": [AIMessage(content=next_task)]
        }

    # 2. INTENT CLASSIFICATION
    # We ask the LLM: What is the user trying to do?
    intent_prompt = f"""
    Analyze the User's last message in the context of a medical triage.
    USER MESSAGE: "{last_user_msg}"
    
    Classify the INTENT into one of these categories:
    - ANSWER: User is providing symptoms, answering "Yes"/"No", or describing condition. (e.g., "No", "I don't have that", "It hurts")
    - RESTART: User explicitly commands to RESET the conversation (e.g., "Start over", "Reset", "Stop everything").
    - CLARIFY: User is confused, asking "what does that mean?", "why?", or repeating the question.
    - IRRELEVANT: User is talking about non-medical things (weather, jokes).
    
    IMPORTANT: "No", "Nope", "I don't think so" are ANSWERS. They are NOT RESTARTs.
    
    OUTPUT JSON ONLY: {{ "intent": "CATEGORY", "reason": "short explanation" }}
    """
    

    
    try:
        import json
        import re
        # Use Fast LLM for Intent
        intent_response = await llm_fast.ainvoke(intent_prompt)
        content = intent_response.content

        
        # Robust Parsing: Find first { and last }
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            json_str = match.group(0)
            intent_data = json.loads(json_str)
            intent = intent_data.get("intent", "ANSWER")
        else:
            # Fallback simple check if JSON fails
            if "RESTART" in content.upper(): intent = "RESTART"
            elif "CLARIFY" in content.upper(): intent = "CLARIFY"
            else: intent = "ANSWER"
            
        print(f"🧠 Strategist Intent: {intent}")
    except Exception as e:
        print(f"Intent Error: {e} | Content: {intent_response.content[:50]}...")
        intent = "ANSWER" # Fallback

    # 3. HANDLE INTENTS
    
    if intent == "RESTART":
        return {
            "triage_decision": "PENDING",
            "safety_checklist": [], # Clear checklist
            "investigated_symptoms": [], # Clear history
            "differential_diagnosis": [],
            "messages": [AIMessage(content="Okay, I have reset the session. Please tell me, what is your main symptom today?")],
            "final_response": "Okay, I have reset the session. Please tell me, what is your main symptom today?"
        }
        
    elif intent == "CLARIFY":
        # The user is confused about the LAST question asking.
        # We should explain it, then re-ask.
        last_question = messages[-1].content if messages and messages[-1].type == 'ai' else "your condition"
        
        explanation_prompt = (
            f'User is confused about this question: "{last_question}". '
            'Explain it simply in 1 sentence, then politely ask it again.'
        )
        explanation = (await llm_strategist.ainvoke(explanation_prompt)).content

        
        return {
            "final_response": explanation,
            "messages": [AIMessage(content=explanation)]
            # We do NOT pop the checklist item yet, so it stays pending
        }

    elif intent == "IRRELEVANT":
        # Politely steer back
        redirect = "I can only help with medical symptoms. Let's focus on your health. "
        if checklist:
            redirect += checklist[0]
        else:
            redirect += "Please tell me your symptoms."
            
        return {
            "final_response": redirect,
            "messages": [AIMessage(content=redirect)]
        }

    # intent == "ANSWER" (Normal Flow)
    # Continues Checklist Logic
    next_task = checklist[0]
    
    # Update investigated list
    current_investigated = state.get("investigated_symptoms", [])
    if next_task not in current_investigated:
        current_investigated.append(next_task)
    
    return {
        "final_response": next_task,
        "investigated_symptoms": current_investigated,
        "messages": [AIMessage(content=next_task)]
    }
