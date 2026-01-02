import sqlite3
import os

DB_PATH = os.path.join("db", "loterias.db")

MEGASENA_VALORES = {
    6: 6.00,
    7: 42.00,
    8: 168.00,
    9: 504.00,
    10: 1260.00,
    11: 2772.00,
    12: 5544.00,
    13: 10296.00,
    14: 18018.00,
    15: 30030.00,
    16: 48048.00,
    17: 74256.00,
    18: 111384.00,
    19: 162792.00,
    20: 232560.00,
}

def criar_ou_atualizar_tabela_precos():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Cria tabela base
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS megasena_precos (
            dezenas INTEGER PRIMARY KEY,
            valor REAL NOT NULL
        )
    """)

    # 🔍 Verifica se coluna atualizado_em existe
    cursor.execute("PRAGMA table_info(megasena_precos)")
    colunas = [col[1] for col in cursor.fetchall()]

    if "atualizado_em" not in colunas:
        cursor.execute("""
            ALTER TABLE megasena_precos
            ADD COLUMN atualizado_em DATETIME
        """)

    # UPSERT (insere ou atualiza)
    for dezenas, valor in MEGASENA_VALORES.items():
        cursor.execute("""
            INSERT INTO megasena_precos (dezenas, valor, atualizado_em)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(dezenas)
            DO UPDATE SET
                valor = excluded.valor,
                atualizado_em = CURRENT_TIMESTAMP
        """, (dezenas, valor))

    conn.commit()
    conn.close()

    print("✅ Tabela 'megasena_precos' criada e valores atualizados com sucesso!")

if __name__ == "__main__":
    criar_ou_atualizar_tabela_precos()
