import os
import time
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
to_number = os.getenv("MY_PHONE_NUMBER")
public_url = os.getenv("PUBLIC_URL")

# IF public_url is empty, try to fetch from ngrok api or hardcode?
# User's ngrok is running. We assume https://ragged-kennedy-attestable.ngrok-free.dev from logs.
if not public_url:
    public_url = "https://ragged-kennedy-attestable.ngrok-free.dev"

client = Client(account_sid, auth_token)

print(f"Calling {to_number} from {twilio_number}...")
print(f"Using Webhook: {public_url}/twilio/incoming")

call = client.calls.create(
    url=f"{public_url}/twilio/incoming",
    to=to_number,
    from_=twilio_number
)

print(f"Call initiated! SID: {call.sid}")
