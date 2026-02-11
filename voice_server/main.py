
from fastapi import FastAPI, HTTPException, WebSocket, UploadFile, File, Form, WebSocketDisconnect, Request
from pydantic import BaseModel
from typing import List, Optional
from langchain_core.messages import HumanMessage
from voice_server.agent.graph import agent_graph
from voice_server.booking_agent.graph import booking_graph
import uuid
import json
import asyncio
import os
import shutil
from voice_server.core.config import settings
import math

# --- GROQ ---
from groq import Groq
client = Groq(api_key=settings.GROQ_API_KEY)

# --- TWILIO ---
from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient

# Custom HTTP Client with increased timeout
http_client = TwilioHttpClient()
http_client.session.timeout = 30  # 30 seconds

twilio_client = Client(
    settings.TWILIO_ACCOUNT_SID, 
    settings.TWILIO_AUTH_TOKEN,
    http_client=http_client
)


app = FastAPI(title="Agentic Doctor V2 - Ported")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REAL-TIME LOGGING ---
import datetime

class LogManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str, level: str = "info"):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = json.dumps({
            "timestamp": now,
            "level": level,
            "message": message
        })
        for connection in list(self.active_connections):
            try:
                await connection.send_text(log_entry)
            except Exception:
                self.active_connections.remove(connection)

log_manager = LogManager()

async def broadcast_log(message: str, level: str = "info"):
    print(f"[{level.upper()}] {message}")
    await log_manager.broadcast(message, level)

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await log_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        log_manager.disconnect(websocket)


@app.post("/twilio/incoming")
async def twilio_incoming(request: Request):
    # Twilio sends form-encoded data. We verify it to avoid 422 errors.
    form_data = await request.form()
    # print(f"Incoming Call from: {form_data.get('From')}")
    await broadcast_log(f"📞 Incoming Call from: {form_data.get('From')}", "info")

    
    # This endpoint handles the TwiML response when Twilio calls this URL
    # We must return XML to tell Twilio to connect to the WebSocket stream
    from fastapi.responses import Response
    
    # We need the public URL to construct the wss:// Stream URL
    # Assuming deployment on ngrok for now
    host = os.getenv("PUBLIC_URL", "ragged-kennedy-attestable.ngrok-free.dev")
    host = host.replace("https://", "").replace("http://", "")
    
    xml_response = f"""
    <Response>
        <Connect>
            <Stream url="wss://{host}/media-stream" />
        </Connect>
    </Response>
    """
    return Response(content=xml_response, media_type="application/xml")


# --- MODELS ---
class ChatRequest(BaseModel):
    message: str
    session_id: str
    target_language: Optional[str] = "English"

class ChatResponse(BaseModel):
    response: str
    decision: Optional[str] = "PENDING"

# --- CHAT ENDPOINTS (From Reference) ---

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    # print(f"DEBUG: Chat endpoint called. Target: '{req.target_language}', Message: '{req.message[:20]}...'")
    await broadcast_log(f"💬 Chat Request: {req.message[:50]}...", "info")

    try:
        config = {"configurable": {"thread_id": req.session_id}}
        
        # Invoke Graph
        result = await agent_graph.ainvoke(
            {"messages": [HumanMessage(content=req.message)]}, 
            config=config
        )
        
        # Robustly extract final response using our fixes
        raw_response = result.get("final_response")
        if not raw_response:
             msgs = result.get("messages", [])
             if msgs: raw_response = msgs[-1].content
             else: raw_response = "I am listening."

        return ChatResponse(
            response=raw_response,
            decision=result.get("triage_decision", "PENDING")
        )
            
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- MERGED VOICE LOGIC ---
import base64
import webrtcvad
import struct
import httpx

# We need DEEPGRAM_KEY
DEEPGRAM_API_KEY = settings.DEEPGRAM_API_KEY

async def send_audio_to_twilio(websocket, stream_sid, text):
    if not text: return
    # print(f"🔊 Speaking: {text}")
    await broadcast_log(f"🔊 Speaking: {text}", "info")

    
    url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=mulaw&sample_rate=8000"
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json={"text": text})
            if resp.status_code == 200:
                chunk_size = 1024
                audio = resp.content
                for i in range(0, len(audio), chunk_size):
                    chunk = audio[i:i+chunk_size]
                    b64 = base64.b64encode(chunk).decode('utf-8')
                    # Check connection open
                    await websocket.send_text(json.dumps({
                        "event": "media", "streamSid": stream_sid, "media": {"payload": b64}
                    }))
                    await asyncio.sleep(0.01) # Pacing
                
                # Mark end
                await websocket.send_text(json.dumps({
                    "event": "mark", "streamSid": stream_sid, "mark": {"name": "speech_end"}
                }))
            else:
                await broadcast_log(f"Deepgram Error: {resp.status_code} - {resp.text}", "error")
    except Exception as e:
        await broadcast_log(f"TTS Error: {e}", "error")


async def transcribe_audio_deepgram(audio_bytes):
    url = "https://api.deepgram.com/v1/listen?model=nova-2&encoding=mulaw&sample_rate=8000"
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": "audio/mulaw"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, content=audio_bytes)
            if resp.status_code == 200:
                data = resp.json()
                transcript = data['results']['channels'][0]['alternatives'][0]['transcript']
                return transcript
    except Exception as e:
        await broadcast_log(f"ASR Error: {e}", "error")


    return ""

def mulaw_to_pcm16(data: bytes) -> bytes:
    res = bytearray()
    for b in data:
        b = ~b & 0xFF
        sign = b & 0x80
        exponent = (b >> 4) & 0x07
        mantissa = b & 0x0F
        sample = (2 * mantissa + 33) << (exponent + 2)
        sample -= 33
        if sign == 0: sample = -sample
        if sample > 32767: sample = 32767
        if sample < -32768: sample = -32768
        res.extend(struct.pack('<h', sample))
    return bytes(res)

def calculate_rms(pcm_data: bytes) -> float:
    """Calculate Root Mean Square amplitude of PCM16 data"""
    if not pcm_data: return 0.0
    
    count = len(pcm_data) // 2
    sum_squares = 0.0
    
    import struct
    # Iterate over 2-byte chunks (16-bit samples)
    for i in range(0, len(pcm_data), 2):
        sample = struct.unpack('<h', pcm_data[i:i+2])[0]
        sum_squares += sample * sample
        
    return math.sqrt(sum_squares / count)

# ... (Websocket Endpoint Re-implementation) ...
@app.websocket("/media-stream")
async def websocket_media_stream(websocket: WebSocket):
    await websocket.accept()
    # print("📞 Call Connected (WebSocket)")
    await broadcast_log("✅ Call Connected (Media Stream)", "success")

    
    session_id = f"call_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": session_id}}
    
    vad = webrtcvad.Vad(2) 
    
    vad_buffer = bytearray()
    collected_audio = bytearray() 
    
    silence_frames = 0
    speech_frames = 0
    is_speaking = False
    
    total_speaking_frames = 0
    MAX_SPEECH_FRAMES = 750 # ~15 seconds max speech per turn
    RMS_THRESHOLD = 300 # Energy threshold (Adjustable: 100-500 is typical noise floor)
    
    MAX_SPEECH_FRAMES = 750 # ~15 seconds max speech per turn
    RMS_THRESHOLD = 300 # Energy threshold (Adjustable: 100-500 is typical noise floor)
    
    stream_sid = None
    
    # STRICT TURN-TAKING STATE
    listening_mode = True 

    
    # Booking State Persistence
    booking_mode = False
    booking_config = {"configurable": {"thread_id": f"booking_{session_id}"}}
    
    try:
        while True:
            data = await websocket.receive_text()
            packet = json.loads(data)
            event = packet.get("event")
            
            if event == "start":
                stream_sid = packet.get("start", {}).get("streamSid")
                # print(f"Stream Started: {stream_sid}")
                await broadcast_log(f"🚀 Stream Started: {stream_sid}", "info")
                
                # Reset listening mode on start
                listening_mode = True


                # Greeting
                # Mute while greeting
                listening_mode = False
                await broadcast_log("🛑 Listening Paused (Agent Speaking)", "warning")
                await send_audio_to_twilio(websocket, stream_sid, "Hello. I am your medical assistant. You can speak now.")

                
            elif event == "media":
                if not listening_mode:
                    # Drop audio packets if not in listening mode
                    continue
                    
                payload = packet.get("media", {}).get("payload")

                if payload:
                    chunk = base64.b64decode(payload)
                    vad_buffer.extend(chunk)
                    
                    if is_speaking:
                        collected_audio.extend(chunk)
                    
                    # Process in 20ms chunks (160 bytes for 8kHz mulaw)
                    while len(vad_buffer) >= 160:
                        frame_mulaw = vad_buffer[:160]
                        del vad_buffer[:160]
                        
                        pcm_frame = mulaw_to_pcm16(frame_mulaw)
                        
                        # --- VAD + RMS LOGIC ---
                        is_speech_vad = vad.is_speech(pcm_frame, 8000)
                        rms = calculate_rms(pcm_frame)
                        
                        # Only count as speech if VAD says Yes AND Energy is high enough
                        if is_speech_vad and rms > RMS_THRESHOLD:
                            speech_frames += 1
                            silence_frames = 0
                        else:
                            # If RMS is low, treat as silence even if VAD flickers
                            silence_frames += 1

                        # Start of speech
                        if speech_frames > 5:
                             if not is_speaking:
                                is_speaking = True
                                # print(f"🗣️ User started speaking... (RMS: {int(rms)})")
                                await broadcast_log(f"🗣️ User started speaking... (RMS: {int(rms)})", "info")
                                total_speaking_frames = 0
                                collected_audio.clear() 
                                collected_audio.extend(frame_mulaw) 
                             else:
                                 if len(collected_audio) < 160000: 
                                     collected_audio.extend(frame_mulaw)
                                 total_speaking_frames += 1

                        # Force Timeout Check
                        if is_speaking and total_speaking_frames > MAX_SPEECH_FRAMES:
                             print("⏱️ Max speech duration reached (15s). Forcing processing.")
                             silence_frames = 100 

                        # End of speech (Silence for > 400ms = 20 frames)
                        if silence_frames > 20 and is_speaking:
                            # print(f"✅ Silence detected ({silence_frames} frames). Processing speech...")
                            await broadcast_log(f"🤫 Silence detected. Processing speech...", "info")
                            
                            # MUTE INPUT IMMEDIATELY
                            listening_mode = False
                            await broadcast_log("🛑 Listening Paused (Agent Thinking)", "warning")
                            
                            is_speaking = False

                            speech_frames = 0
                            silence_frames = 0
                            total_speaking_frames = 0
                            
                            # Transcribe
                            if len(collected_audio) > 800: # Min duration check ~100ms
                                print(f"Processing audio buffer: {len(collected_audio)} bytes")
                                transcript = await transcribe_audio_deepgram(bytes(collected_audio))
                                # print(f"📝 Transcript: {transcript}")
                                await broadcast_log(f"📝 Transcript: {transcript}", "success")

                                
                                if transcript and len(transcript) > 1:
                                    
                                    if booking_mode:
                                        # print(f"📅 processing Booking... Mode: {booking_mode}, Thread: {booking_config}")
                                        await broadcast_log(f"📅 Processing Booking...", "info")
                                        # Invoke booking agent directly
                                        booking_result = await booking_graph.ainvoke(
                                            {"messages": [HumanMessage(content=transcript)]},
                                            config=booking_config
                                        )
                                        
                                        response_text = booking_result.get("final_response")
                                        if not response_text:
                                            msgs = booking_result.get("messages", [])
                                            if msgs: response_text = msgs[-1].content
                                            else: response_text = "I heard you."
                                            
                                        # Check completion
                                        if booking_result.get("booking_stage") == "complete":
                                            # print("✅ Booking Complete. Ending Call.")
                                            await broadcast_log("✅ Booking Complete.", "success")
                                            # We could hang up here or just say goodbye
                                            
                                    else:
                                        # --- CLINICAL MODE ---
                                        # print("🤖 Invoking Clinical Agent...")
                                        await broadcast_log("🤖 Invoking Clinical Agent...", "info")
                                        result = await agent_graph.ainvoke(
                                            {"messages": [HumanMessage(content=transcript)]}, 
                                            config=config
                                        )
                                        
                                        # Check if clinical assessment is complete
                                        triage_decision = result.get("triage_decision", "PENDING")
                                        assessment_complete = result.get("assessment_complete", False)
                                        
                                        # Trigger booking agent if:
                                        # 1. Emergency detected, OR
                                        # 2. Assessment explicitly marked as complete (summary generated)
                                        should_book = (triage_decision == "EMERGENCY") or assessment_complete
                                        
                                        if should_book:
                                            # print("📅 Triggering Booking Agent...")
                                            await broadcast_log("⚠️ Emergency/Done -> Switching to Booking Agent", "warning")
                                            booking_mode = True # SWITCH MODE PERMANENTLY
                                            
                                            
                                            # Prepare booking context
                                            medical_summary = result.get("final_response", "Assessment complete.")
                                            
                                            # Invoke booking agent (Initial)
                                            booking_result = await booking_graph.ainvoke(
                                                {
                                                    "messages": [HumanMessage(content=transcript)], # Context
                                                    "triage_decision": triage_decision,
                                                    "medical_summary": medical_summary,
                                                    "booking_stage": "initial",
                                                    "doctor_name": "Dr. Smith"
                                                },
                                                config=booking_config
                                            )
                                            
                                            booking_response = booking_result.get("final_response")
                                            if not booking_response:
                                                msgs = booking_result.get("messages", [])
                                                if msgs: booking_response = msgs[-1].content
                                                else: booking_response = "How can I help you book?"

                                            # COMBINE: Clinical Summary + Booking Greeting
                                            # This ensures the user hears the summary first
                                            if medical_summary:
                                                response_text = f"{medical_summary} ... {booking_response}"
                                            else:
                                                response_text = booking_response

                                        else:
                                            # Continue with clinical agent response
                                            response_text = result.get("final_response")
                                            if not response_text:
                                                 msgs = result.get("messages", [])
                                                 if msgs: response_text = msgs[-1].content
                                                 else: response_text = "I heard you."
                                    
                                    await send_audio_to_twilio(websocket, stream_sid, response_text)
                                else:
                                    # print("⚠️ No transcript detected. (Likely noise)")
                                    # FAILURE CASE: We paused listening, but we aren't going to speak.
                                    # We MUST resume listening so the user can try again.
                                    listening_mode = True
                                    await broadcast_log("⚠️ No speech detected. Listening Resumed.", "warning")

                                    
                            collected_audio.clear()

            elif event == "mark":
                mark_name = packet.get("mark", {}).get("name")
                if mark_name == "speech_end":
                    listening_mode = True
                    await broadcast_log("👂 Listening Resumed", "success")
                    # Clear buffer to avoid processing old audio
                    collected_audio.clear()
                    vad_buffer.clear()
                    is_speaking = False
                    speech_frames = 0
                    silence_frames = 0

            elif event == "stop":
                # print("Call Ended.")
                await broadcast_log("🛑 Call Ended (Twilio Stop Event)", "warning")
                break

                
    except WebSocketDisconnect:
        # print("WebSocket Disconnected")
        await broadcast_log("🔌 WebSocket Disconnected", "error")

    except Exception as e:
        print(f"WS Error: {e}")

# --- MAKE CALL ENDPOINT ---
class MakeCallRequest(BaseModel):
    to_number: str

@app.post("/api/make_call")
async def make_call_endpoint(req: MakeCallRequest):
    try:
        to_number = req.to_number
        if not to_number:
            raise HTTPException(status_code=400, detail="Phone number is required")
        
        # Get public URL from env or existing logic
        public_url = os.getenv("PUBLIC_URL")
        if not public_url:
            # Fallback for dev - try to find ngrok if not set
            # In production, this should always be set
            public_url = "https://ragged-kennedy-attestable.ngrok-free.dev"

        from_number = settings.TWILIO_PHONE_NUMBER
        
        await broadcast_log(f"Make Call -> {to_number}", "info")

        call = twilio_client.calls.create(
            url=f"{public_url}/twilio/incoming",
            to=to_number,
            from_=from_number
        )
        
        return {"message": "Call initiated", "call_sid": call.sid}
    except Exception as e:
        print(f"Make Call Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- MEDICATION REMINDER AGENT ---

class ReminderRequest(BaseModel):
    to_number: str
    message: str

@app.post("/api/make_reminder_call")
async def make_reminder_call(req: ReminderRequest):
    try:
        if not req.to_number or not req.message:
            raise HTTPException(status_code=400, detail="Phone number and message are required")
        
        public_url = os.getenv("PUBLIC_URL")
        if not public_url:
            public_url = "https://ragged-kennedy-attestable.ngrok-free.dev"

        from_number = settings.TWILIO_PHONE_NUMBER
        
        # URL Encod the message so it passes safely in the URL
        import urllib.parse
        encoded_message = urllib.parse.quote(req.message)
        
        # webhook_url will be called by Twilio when the call connects
        webhook_url = f"{public_url}/twilio/incoming_reminder?message={encoded_message}"
        
        await broadcast_log(f"Make Reminder Call -> {req.to_number} | Message: {req.message}", "info")

        
        call = twilio_client.calls.create(
            url=webhook_url,
            to=req.to_number,
            from_=from_number
        )
        
        return {"message": "Reminder call initiated", "call_sid": call.sid}
    except Exception as e:
        print(f"Reminder Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/twilio/incoming_reminder")
async def incoming_reminder(request: Request):
    """
    Twilio Webhook for the 'Medication Reminder Agent'.
    It reads the 'message' query param and speaks it.
    """
    params = request.query_params
    message = params.get("message", "This is a reminder from your doctor.")
    
    await broadcast_log(f"💊 Spoken Reminder: {message}", "info")

    # Twilio TwiML

    xml_response = f"""
    <Response>
        <Pause length="1"/>
        <Say voice="Polly.Joanna-Neural">Hello. This is an automated medication reminder.</Say>
        <Pause length="1"/>
        <Say voice="Polly.Joanna-Neural">{message}</Say>
        <Pause length="1"/>
        <Say voice="Polly.Joanna-Neural">Goodbye.</Say>
    </Response>
    """
    from fastapi.responses import Response
    return Response(content=xml_response, media_type="application/xml")

# --- STATIC FILES FOR UI ---
from fastapi.staticfiles import StaticFiles
# Ensure directory exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
