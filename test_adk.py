import requests
import json

base_url = "http://localhost:8000"
try:
    session_resp = requests.post(f"{base_url}/apps/head_chef/users/user/sessions")
    print("Session:", session_resp.status_code, session_resp.text)
    if session_resp.status_code == 200:
        session_id = session_resp.json().get("session_id")
        print("Session ID:", session_id)
        
        # Try sending a message
        payload = {
            "app_name": "head_chef",
            "user_id": "user",
            "session_id": session_id,
            "message": "Hello!"
        }
        sse_resp = requests.post(f"{base_url}/run_sse", json=payload, stream=True)
        print("SSE Status:", sse_resp.status_code)
        for line in sse_resp.iter_lines():
            if line:
                print(line.decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
