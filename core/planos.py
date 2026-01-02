import sqlite3
import os

DB_PATH = os.path.join("db", "loterias.db")  # ajuste se necessário

def carregar_planos_ativos():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            codigo,
            nome,
            descricao,
            valor,
            validade_dias
        FROM planos
        WHERE ativo = 1
        ORDER BY valor ASC
    """)

    planos = cursor.fetchall()
    conn.close()

    return planos
