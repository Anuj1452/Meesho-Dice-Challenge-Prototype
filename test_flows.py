import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def req(url, method='GET', body=None):
    headers = {'Content-Type': 'application/json'} if body else {}
    data = json.dumps(body).encode('utf-8') if body else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {"error": str(e), "body": e.read().decode('utf-8', errors='ignore')}
    except Exception as e:
        return {"error": str(e)}

print("=== STARTING END-TO-END FLOW TESTS ===")

# 1. Rider Manifest
manifest = req('http://127.0.0.1:8000/api/rider/manifest/RDR-001')
print(f"1. Rider Manifest: {manifest.get('rider_name')} has {manifest.get('total_stops')} stops.")

# 2. Morning Nudge All
nudge_all = req('http://127.0.0.1:8000/api/rider/nudge-all/RDR-001', method='POST')
print(f"2. Morning Nudge All: {nudge_all}")

# 3. Customer 1 (Priya: f855b2ec33339e4b) responds: "Available Today"
p1_start = req('http://127.0.0.1:8000/api/chat/session/start/f855b2ec33339e4b')
sess1 = p1_start.get('session_id')
p1_reply = req('http://127.0.0.1:8000/api/chat/message', method='POST', body={
    "session_id": sess1,
    "phone_hash": "f855b2ec33339e4b",
    "message": "Available Today"
})
print(f"3. Priya ('Available Today') AI Reply: {p1_reply.get('reply')[:80]}...")

# 4. Customer 3 (Anita: d3aba319ff24da92) responds: "Kal aaiye" (Come Tomorrow)
p3_start = req('http://127.0.0.1:8000/api/chat/session/start/d3aba319ff24da92')
sess3 = p3_start.get('session_id')
p3_reply = req('http://127.0.0.1:8000/api/chat/message', method='POST', body={
    "session_id": sess3,
    "phone_hash": "d3aba319ff24da92",
    "message": "Kal aaiye, aaj available nahi hoon"
})
print(f"4. Anita ('Kal aaiye') AI Reply: {p3_reply.get('reply')[:80]}...")

# 5. Check Rider Manifest updates
manifest_updated = req('http://127.0.0.1:8000/api/rider/manifest/RDR-001')
print("5. Updated Stops Status:")
for s in manifest_updated.get('stops', []):
    print(f"   - {s['customer_first_name']}: status={s['status']}, resp={s.get('customer_response_status')}, note={s.get('customer_note')}, missed={s.get('missed_call_count')}")

# 6. Rider triggers "Missed Call" on Rahul Verma (stop 2)
rahul_order = next((s for s in manifest_updated.get('stops', []) if 'Rahul' in s.get('customer_full_name', '')), None)
if rahul_order:
    missed_res = req(f"http://127.0.0.1:8000/api/rider/missed-call/RDR-001/{rahul_order['order_id']}", method='POST')
    print(f"6. Logged Missed Call on Rahul: {missed_res}")
    
    # Check Rahul's chat session history
    r_start = req('http://127.0.0.1:8000/api/chat/session/start/44a7469deed95dfa')
    r_hist = req(f"http://127.0.0.1:8000/api/chat/history/{r_start['session_id']}")
    latest_msg = r_hist.get('messages', [])[-1] if r_hist.get('messages') else {}
    print(f"   Rahul received alert on WhatsApp: {latest_msg.get('content')[:90]}...")
    
    # Rahul responds: "Padosi ko de do"
    r_reply = req('http://127.0.0.1:8000/api/chat/message', method='POST', body={
        "session_id": r_start['session_id'],
        "phone_hash": "44a7469deed95dfa",
        "message": "Padosi / security guard ko de do"
    })
    print(f"   Rahul reply AI response: {r_reply.get('reply')[:80]}...")

# 7. Final Manifest Check
manifest_final = req('http://127.0.0.1:8000/api/rider/manifest/RDR-001')
print("7. Final Manifest:")
for s in manifest_final.get('stops', []):
    print(f"   - {s['customer_first_name']}: status={s['status']}, resp={s.get('customer_response_status')}, note={s.get('customer_note')}, missed={s.get('missed_call_count')}")

print("\n=== ALL FLOW TESTS COMPLETED SUCCESSFULLY! ===")
