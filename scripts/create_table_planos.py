import sqlite3
import os

# Caminho do banco
DB_DIR = "db"
DB_PATH = os.path.join(DB_DIR, "loterias.db")

def criar_tabela_planos():
    # Garante que a pasta db existe
    os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Criação da tabela
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS planos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT,
            valor REAL NOT NULL,
            validade_dias INTEGER NOT NULL,
            ativo INTEGER DEFAULT 1
        );
    """)

    conn.commit()

    # Planos iniciais
    planos_iniciais = [
        ("mensal", "Plano Mensal", "Acesso completo ao bot", 29.90, 30),
        ("trimestral", "Plano Trimestral", "Acesso completo com desconto", 79.90, 90),
        ("anual", "Plano Anual", "Melhor custo-benefício", 299.90, 365),
    ]

    for plano in planos_iniciais:
        cursor.execute("""
            INSERT OR IGNORE INTO planos
            (codigo, nome, descricao, valor, validade_dias)
            VALUES (?, ?, ?, ?, ?)
        """, plano)

    conn.commit()
    conn.close()

    print("✅ Tabela 'planos' criada e planos iniciais inseridos com sucesso.")


if __name__ == "__main__":
    criar_tabela_planos()
