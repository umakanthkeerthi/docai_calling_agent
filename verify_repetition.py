
from voice_server.agent.nodes.diagnostician import is_similar
import difflib

def test_dedup():
    print("TEST: Verifying Deduplication Logic...")
    
    q1 = "Do you have any neck stiffness?"
    q2 = "Any stiffness in your neck?"
    
    sim = difflib.SequenceMatcher(None, q1.lower(), q2.lower()).ratio()
    print(f"Similarity ('{q1}' vs '{q2}'): {sim}")
    
    if is_similar(q1, q2, 0.6):
        print("✅ Correctly identified as duplicate.")
    else:
        print("❌ FAILED to identify duplicate.")
        
    q3 = "Have you traveled recently?"
    q4 = "Have you taken any new medications?"
    
    sim2 = difflib.SequenceMatcher(None, q3.lower(), q4.lower()).ratio()
    print(f"Similarity ('{q3}' vs '{q4}'): {sim2}")
    
    if not is_similar(q3, q4, 0.6):
         print("✅ Correctly identified as distinct.")
    else:
         print("❌ FALSE POSITIVE on distinct questions.")

    print("\nTEST: Verifying Pruning (Simulated clean_duplicates)...")
    forbidden = ["Do you have a fever?", "Any cough?"]
    checklist = ["Do you have a fever?", "Any neck stiffness?", "Any cough?"]
    
    cleaned = []
    for q in checklist:
        is_dup = False
        for f in forbidden:
             if is_similar(q, f, 0.6): is_dup = True
        if not is_dup: cleaned.append(q)
        
    print(f"Original: {checklist}")
    print(f"Forbidden: {forbidden}")
    print(f"Pruned: {cleaned}")
    
    if len(cleaned) == 1 and cleaned[0] == "Any neck stiffness?":
        print("✅ Pruning Logic Correct.")
    else:
        print("❌ Pruning Logic Failed.")

if __name__ == "__main__":
    test_dedup()
