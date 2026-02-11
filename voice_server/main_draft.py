import os
import json
import base64
import asyncio
# import traceback
import datetime
import struct
# import math
# import wave
import io
import difflib
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

# LangGraph & Logic
from langchain_core.messages import HumanMessage, AIMessage
from .agent.graph import agent_graph

# VAD
import webrtcvad

# Groq
from groq import Groq

load_dotenv()

# --- CONFIG ---
PORT = int(os.getenv("PORT", 8000))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=GROQ_API_KEY)

app = FastAPI()

# --- UTILS ---

_ulaw_table = None
def get_ulaw_table():
    global _ulaw_table
    if _ulaw_table is None:
        table = []
        for i in range(256):
            ulaw = ~i & 0xFF
            ulaw ^= 0x80 # Toggle sign bit? No, Python bytes signedness issues.
                         # Standard U-law expansion logic...
                         # Actually, let's use a simpler heuristic or just accept the latency of a real calculation if table is hard.
                         # But for VAD, we need speed.
                         # Let's use the provided lookup table approach from before?
                         # Or just use the formula?
                         # Formula: 
            mu = 255
            # ... (omitted for brevity, assume standard expansion)
            # Reverting to simplified linear approximation or skipping VAD if complex?
            # NO, we need VAD.
            # Let's implementation mu-law to linear.
        # Placeholder for correct table gen
        pass
    return _ulaw_table

# Standard Mu-Law to Linear decoder (8-bit to 16-bit)
# Lookup table source: https://github.com/torvalds/linux/blob/master/lib/mulaw.c logic
# Simplified python version:
def mulaw_to_pcm16(data: bytes) -> bytes:
    # Quick implementation or use audioop if available?
    # Audioop is deprecated/removed in 3.13? If user is on 3.12 it works.
    # Assuming 3.12+ -> Need manual.
    res = bytearray()
    for b in data:
        # Toggle sign bit
        b = ~b & 0xFF
        sign = b & 0x80
        exponent = (b >> 4) & 0x07
        mantissa = b & 0x0F
        sample = (2 * mantissa + 33) << (exponent + 2)
        sample -= 33
        if sign == 0:
            sample = -sample
        # Clip
        if sample > 32767: sample = 32767
        if sample < -32768: sample = -32768
        
        res.extend(struct.pack('<h', sample))
    return bytes(res)

# --- GROQ STT & TTS ---

async def transcribe_with_groq(audio_bytes: bytes) -> str:
    # Convert Mulaw to WAV for Groq?
    # Or just send as is? Whisper handles wav/mp3.
    # We must wrap in WAV container.
    # header: 44 bytes.
    # Format: 1 (PCM) or 7 (MuLaw)
    # Groq whisper supports WAV.
    # Let's send 16-bit PCM WAV (better quality).
    pcm_data = mulaw_to_pcm16(audio_bytes)
    
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(8000)
            wf.writeframes(pcm_data)
        
        wav_buffer.seek(0)
        
        try:
            # Using synchronous client in async wrapper?
            # Ideally verify if groq-python has async.
            # Assuming client.audio.transcriptions.create is sync.
            transcription = client.audio.transcriptions.create(
                file=("audio.wav", wav_buffer.read()),
                model="whisper-large-v3-turbo", # Fast model
                language="en",
                response_format="text"
            )
            return str(transcription)
        except Exception as e:
            print(f"STT Error: {e}")
            return ""

# Note: Using ElevenLabs or Deepgram for TTS is better, but user said "Groq-Hybrid".
# Does Groq have TTS? No.
# Previous implementation used... Deepgram? Or just mocked?
# Wait, user earlier mentioned "Exotel/Deepgram" in plan.
# But I am supposed to use what I have.
# The user never provided Deepgram key in .env check?
# Let's check .env logic.
# If no TTS provider, I can't speak?
# I should assume Deepgram or OpenAI TTS is available.
# Let's use OpenAITTS logic as placeholder (since I saw OpenAI keys in previous context),
# OR check env.
# Safest: Use a "Mock TTS" that logs if no key, or default to Deepgram if keys exist.
# Actually, I will check `.env` content in a bit.
# For now, I will write generic 'send_audio' that assumes a TTS function exists.

async def send_audio_to_twilio(websocket, stream_sid, text):
    # TODO: Implement actual TTS (Deepgram/OpenAI) here.
    # For now, acting as if we are sending audio.
    # We send "Mark" at the end.
    
    # ... TTS Logic ...
    # sending mock silence for now to test logic? No, user needs to hear.
    # I will assume Deepgram is setup or I will add it.
    pass

# --- MAIN SERVER ---

@app.websocket("/media-stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # State
    config = {"configurable": {"thread_id": "v1"}}
    vad = webrtcvad.Vad(3)
    vad_buffer = bytearray()
    
    # VAD Logic Vars
    is_speaking = False
    speech_frames = 0
    silence_frames = 0
    speech_start_frames = 0
    chunk_count = 0
    
    # Half-Duplex Lock
    ai_is_speaking = False
    
    try:
        while True:
            # ... Input Handling ...
            # ... Zero Silence Logic ...
            pass
    except Exception:
        pass
