
import os
import chromadb
from typing import Dict, Any, List
from langchain_groq import ChatGroq
from voice_server.core.config import settings

chroma_client = chromadb.PersistentClient(path=settings.DB_PATH)
# Use get_or_create to avoid errors if ingestion hasn't run
col_rules = chroma_client.get_or_create_collection("decision_rules")

async def retrieval_node(state: Dict[str, Any]) -> Dict[str, Any]:
    messages = state.get("messages", [])
    last_msg = messages[-1].content
    
    print(f"🔎 Retrieving for: {last_msg}")
    
    # Chroma query is sync, but we can wrap it or just leave it if fast.
    # ideally await asyncio.to_thread
    import asyncio
    
    def query():
        return col_rules.query(
            query_texts=[last_msg],
            n_results=3
        )
        
    results = await asyncio.to_thread(query)
    
    docs = []
    if results['documents']:
        for i, doc in enumerate(results['documents'][0]):
            docs.append(doc)
            
    return {"retrieved_protocols": docs}

