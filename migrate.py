import sqlite3

con = sqlite3.connect('valmo_mitra.db')
cur = con.cursor()
cols = [r[1] for r in cur.execute('PRAGMA table_info(orders)').fetchall()]
print('Current order cols:', cols)

if 'missed_call_count' not in cols:
    cur.execute('ALTER TABLE orders ADD COLUMN missed_call_count INTEGER DEFAULT 0')
    print('Added missed_call_count')

if 'customer_response_status' not in cols:
    cur.execute("ALTER TABLE orders ADD COLUMN customer_response_status VARCHAR(50) DEFAULT ''")
    print('Added customer_response_status')

con.commit()
con.close()
print('Schema successfully validated and ready!')
