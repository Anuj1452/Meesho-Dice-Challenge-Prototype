from backend.models.database import init_db, get_session_factory
from backend.sim.seed_data import seed_database, CUSTOMERS, _hash
import sys
sys.stdout.reconfigure(encoding='utf-8')

init_db()
SessionLocal = get_session_factory()
db = SessionLocal()
result = seed_database(db)
db.close()
print('Seeded:', result)

print()
print('=== DEMO USER PHONE HASHES (paste these into the frontend) ===')
scenarios = [
    'IN_TRANSIT + COD       --> ask: kahan hai mera order',
    'OUT_FOR_DELIVERY HIGH  --> ask: rider kab aayega, note add karo',
    'FAILED_ATTEMPT         --> ask: aaj delivery kyun nahi hui',
    'AT_HUB + COD           --> ask: online pay karna hai',
    'RESCHEDULED x2 HIGH    --> ask: yeh kab aayega (escalation)',
]
for i, c in enumerate(CUSTOMERS):
    h = _hash(c['phone'])
    print(f"  [{i+1}] {c['name']:15s} | {c['phone']} | hash: {h}")
    print(f"       Scenario: {scenarios[i]}")
