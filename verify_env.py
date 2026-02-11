import sys

print("System Check: Verifying all imports...")

try:
    print("Checking core...")
    import os
    import json
    import dotenv
    from fastapi import FastAPI
    import uvicorn
    import websockets
    
    print("Checking LangChain Core...")
    import langchain_core
    from langchain_core.messages import HumanMessage, AIMessage

    print("Checking Groq...")
    import groq
    from langchain_groq import ChatGroq

    # OpenAI removed (Using Groq)

    print("Checking Retrieval (Chroma/HuggingFace)...")
    import chromadb
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    print("Checking Voice...")
    import twilio
    import webrtcvad

    print("ALL DEPENDENCIES INSTALLED SUCCESSFULLY! ✅")

except ImportError as e:
    print(f"\n❌ CRITICAL ERROR: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ UNKNOWN ERROR: {e}")
    sys.exit(1)
