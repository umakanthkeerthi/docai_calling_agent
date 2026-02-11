
import chromadb
import os
import re
# from pypdf import PdfReader 
# Updating import to follow requirements (pypdf might need install, but user has verify_env.py)
# If pypdf is missing, this script will fail. We added it to requirements.txt
try:
    from pypdf import PdfReader
except ImportError:
    print("pypdf not installed. Please run: pip install pypdf")
    exit(1)

from typing import List, Dict, Any
from uuid import uuid4

# --- CONFIGURATION ---
# We assume data is in c:\docai_calling_agent\data
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "nhsrc_guidelines.pdf")
DB_PATH = os.path.join(os.path.dirname(__file__), "chroma_db_new")

# --- PARSER LOGIC ---

class SmartChunker:
    """
    Parses NHSRC Guidelines into semantic chunks.
    """
    def __init__(self):
        # We define "Topics" that we expect to find in the manual
        self.TOPICS = [
            "Fever", "Cough", "Diarrhoea", "Diarrhea", "Vomiting", 
            "Skin Infection", "Burns", "Wounds", "Bites", "Poisoning",
            "Epilepsy", "Seizures", "Unconsciousness", "Hypertension", 
            "Diabetes", "Chest Pain", "Stroke", "First Aid"
        ]
        
        self.SECTION_MARKERS = {
            "RED_FLAGS": ["danger signs", "referral", "when to refer", "emergency", "immediate check"],
            "MANAGEMENT": ["management", "treatment", "action plan", "first aid measures"],
            "ASSESSMENT": ["assessment", "signs and symptoms", "clinical features", "diagnosis"]
        }

    def chunk_pdf(self, pdf_path: str) -> List[Dict]:
        if not os.path.exists(pdf_path):
            print(f"❌ PDF not found at {pdf_path}")
            return []

        reader = PdfReader(pdf_path)
        full_text = ""
        
        print("📖 Reading PDF...")
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
            
        print(f"✅ Extracted {len(full_text)} characters.")
        
        # 1. Split into Broad Topics
        chunks = []
        lines = full_text.split('\n')
        
        current_topic = "General Introduction"
        current_chunk_buffer = []
        current_section_type = "REFERENCE" # Default
        
        for line in lines:
            clean_line = line.strip()
            if not clean_line:
                continue

            # 1. Detect New Topic Switch
            is_new_topic = False
            for topic in self.TOPICS:
                if len(clean_line) < 50 and topic.upper() in clean_line.upper():
                    if clean_line.isupper() or "Unit" in clean_line or "Module" in clean_line:
                        if current_chunk_buffer:
                            chunks.append(self._create_chunk(current_topic, current_section_type, current_chunk_buffer))
                            current_chunk_buffer = []
                        
                        current_topic = topic
                        current_section_type = "REFERENCE"
                        is_new_topic = True
                        print(f"  -> Found Topic: {current_topic}")
                        break
            
            if is_new_topic:
                continue

            # 2. Detect Section Switch
            is_new_section = False
            for section_type, keywords in self.SECTION_MARKERS.items():
                for kw in keywords:
                    if kw in clean_line.lower() and len(clean_line) < 60:
                        if current_chunk_buffer:
                            chunks.append(self._create_chunk(current_topic, current_section_type, current_chunk_buffer))
                            current_chunk_buffer = []
                        
                        current_section_type = section_type
                        is_new_section = True
                        break
                if is_new_section: break
            
            # 3. Add Line to Buffer
            current_chunk_buffer.append(clean_line)
            
            # 4. forced split if too long (fallback)
            if len(current_chunk_buffer) > 20: 
                 chunks.append(self._create_chunk(current_topic, current_section_type, current_chunk_buffer))
                 current_chunk_buffer = []

        # Flush final
        if current_chunk_buffer:
            chunks.append(self._create_chunk(current_topic, current_section_type, current_chunk_buffer))
            
        return chunks

    def _create_chunk(self, topic, section_type, lines):
        text = "\n".join(lines)
        db_type = "reference_info"
        if section_type == "RED_FLAGS" or section_type == "MANAGEMENT":
            db_type = "decision_rules"
        elif section_type == "REFERENCE":
            if len(text) < 500 and "Introduction" in text:
                db_type = "protocol_summaries"
            else:
                db_type = "reference_info"

        return {
            "content": text,
            "metadata": {
                "protocol": topic,
                "section": section_type,
                "type": db_type, 
                "symptoms": topic 
            }
        }

# --- INGESTION MAIN ---

def ingest():
    print("🚀 Starting Semantic Ingestion...")
    
    # 1. Initialize Clients
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    # In strict mode, get_collection errors if not found. Let's use get_or_create_collection
    col_summaries = chroma_client.get_or_create_collection("protocol_summaries")
    col_rules = chroma_client.get_or_create_collection("decision_rules")
    col_refs = chroma_client.get_or_create_collection("reference_info")
    
    # In strict mode, get_collection errors if not found. Let's use get_or_create_collection
    col_summaries = chroma_client.get_or_create_collection("protocol_summaries")
    col_rules = chroma_client.get_or_create_collection("decision_rules")
    col_refs = chroma_client.get_or_create_collection("reference_info")

    # 2. Parse PDF
    chunker = SmartChunker()
    chunks = chunker.chunk_pdf(DATA_PATH)
    print(f"📦 Generated {len(chunks)} semantic chunks.")
    
    # 3. Upload to Chroma
    for i, chunk in enumerate(chunks):
        target_col = col_refs
        if chunk['metadata']['type'] == 'protocol_summaries':
            target_col = col_summaries
        elif chunk['metadata']['type'] == 'decision_rules':
            target_col = col_rules
            
        final_text = f"PROTOCOL: {chunk['metadata']['protocol']}\nSECTION: {chunk['metadata']['section']}\nCONTENT:\n{chunk['content']}"
        
        target_col.add(
            documents=[final_text],
            metadatas=[chunk['metadata']],
            ids=[f"chunk_{i}_{uuid4().hex[:8]}"]
        )
        
        if i % 10 == 0:
            print(f"   Indexed {i}/{len(chunks)} chunks...", end='\r')
            
    print(f"\n✅ Ingestion Complete! DB is ready at {DB_PATH}")

if __name__ == "__main__":
    ingest()
