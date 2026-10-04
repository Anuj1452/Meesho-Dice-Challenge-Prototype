import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

def get(url):
    try:
        r = urllib.request.urlopen(url, timeout=5)
        return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return {"ERROR": str(e)}

def post(url, body):
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        r = urllib.request.urlopen(req, timeout=10)
        return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return {"ERROR": str(e)}

print("=== BACKEND AUDIT ===\n")

# 1. Health
h = get("http://127.0.0.1:8000/health")
print(f"1. /health => {h}")

# 2. Rider manifest
m = get("http://127.0.0.1:8000/api/rider/manifest/RDR-001")
print(f"\n2. /rider/manifest/RDR-001 => rider={m.get('rider_name')}, stops={len(m.get('stops', []))}")
for s in m.get("stops", []):
    print(f"   [{s.get('customer_first_name'):10s}] status={s.get('status'):25s} cod={s.get('is_cod')} delivered={s.get('is_delivered')} cash={s.get('cash_to_collect')}")
    print(f"             order_id={s.get('order_id')} awb={s.get('awb')}")

# 3. My Day
d = get("http://127.0.0.1:8000/api/rider/myday/RDR-001")
print(f"\n3. /rider/myday/RDR-001 => delivered={d.get('delivered_stops')} pending={d.get('pending_stops')}")

# 4. Chat session start - Priya (IN_TRANSIT)
s = get("http://127.0.0.1:8000/api/chat/session/start/f855b2ec33339e4b")
print(f"\n4. Chat session (Priya) => customer={s.get('customer')} orders={len(s.get('orders', []))}")

# 5. Chat message - Priya asks status
c = post("http://127.0.0.1:8000/api/chat/message", {
    "session_id": "audit_001", "phone_hash": "f855b2ec33339e4b", "message": "mera order kahan hai?"
})
print(f"\n5. Chat msg Priya => reply={c.get('reply', '')[:120]}")
print(f"   buttons={[b['title'] for b in c.get('buttons', [])]}")

# 6. Ops metrics
op = get("http://127.0.0.1:8000/api/ops/metrics/VMC-DEL-01")
print(f"\n6. /ops/metrics/VMC-DEL-01 => {op.get('metrics', {})}")

# 7. Review queue
q = get("http://127.0.0.1:8000/api/ops/queue/VMC-DEL-01")
print(f"\n7. /ops/queue => {len(q.get('queue', []))} items")

print("\n=== AUDIT DONE ===")
