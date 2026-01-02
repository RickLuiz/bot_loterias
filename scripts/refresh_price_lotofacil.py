import sqlite3
import os

DB_PATH = os.path.join("db", "loterias.db")

# Valores oficiais atuais da Lotofácil
LOTOFACIL_VALORES = {
    15: 3.50,
    16: 56.00,
    17: 476.00,
    18: 2856.00,
    19: 13566.00,
    20: 54264.00,
}

def criar_ou_atualizar_tabela_precos_lotofacil():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Cria tabela se não existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lotofacil_precos (
            dezenas INTEGER PRIMARY KEY,
            valor REAL NOT NULL,
            atualizado_em DATETIME
        )
    """)

    # Verifica se coluna atualizado_em existe
    cursor.execute("PRAGMA table_info(lotofacil_precos)")
    colunas = [col[1] for col in cursor.fetchall()]

    if "atualizado_em" not in colunas:
        cursor.execute("""
            ALTER TABLE lotofacil_precos
            ADD COLUMN atualizado_em DATETIME
        """)

    # Inserir ou atualizar
    for dezenas, valor in LOTOFACIL_VALORES.items():
        cursor.execute("""
            INSERT INTO lotofacil_precos (dezenas, valor, atualizado_em)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(dezenas)
            DO UPDATE SET
                valor = excluded.valor,
                atualizado_em = CURRENT_TIMESTAMP
        """, (dezenas, valor))

    conn.commit()
    conn.close()
    print("✅ Lotofácil: tabela de preços criada/atualizada com valores oficiais!")

if __name__ == "__main__":
    criar_ou_atualizar_tabela_precos_lotofacil()
