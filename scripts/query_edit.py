import sqlite3
import os

DB_PATH = os.path.join("db", "loterias.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
               drop table usuarios;
               
               """)

conn.commit()
conn.close()

print("✅ Query executada!")
