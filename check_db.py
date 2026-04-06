import sqlite3
import os

DB_PATH = r'c:\Users\TECNOCEL\tecnocel-crm\tecnocel.db'

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} no existe.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    negocios = conn.execute('SELECT id, nombre_negocio, email, password_hash FROM negocios').fetchall()
    
    print(f"Total negocios: {len(negocios)}")
    for row in negocios:
        print(dict(row))
    
    conn.close()

if __name__ == "__main__":
    check_db()
