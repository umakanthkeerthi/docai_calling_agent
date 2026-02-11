import requests
import json
import os

def get_ngrok_url():
    try:
        # Ngrok client API is usually at port 4040
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
        if response.status_code == 200:
            data = response.json()
            tunnels = data.get("tunnels", [])
            for tunnel in tunnels:
                if tunnel.get("proto") == "https":
                    public_url = tunnel.get("public_url")
                    print(public_url)
                    return public_url
    except Exception:
        pass
    return None

if __name__ == "__main__":
    url = get_ngrok_url()
    if not url:
        # If 4040 fails, maybe ngrok isn't running.
        print("FAIL: Ngrok not found.")
        exit(1)
    else:
        # Update .env if possible? Or just print for batch file.
        pass
