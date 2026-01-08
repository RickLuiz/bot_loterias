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
            validade_dias INTEGER,
            tipo TEXT NOT NULL DEFAULT 'periodo',
            creditos INTEGER DEFAULT 0,
            ativo INTEGER DEFAULT 1
        );
    """)

    conn.commit()

    # =============================
    # PLANOS INICIAIS
    # =============================
    planos_iniciais = [
        # 🔵 PLANOS POR PERÍODO
        ("mensal", "Plano Mensal", "Acesso completo ao bot", 29.90, 30, "periodo", 0),
        ("trimestral", "Plano Trimestral", "Acesso completo com desconto", 79.90, 90, "periodo", 0),
        ("anual", "Plano Anual", "Melhor custo-benefício", 299.90, 365, "periodo", 0),

        # 🟢 PLANO PRÉ-PAGO (CRÉDITOS)
        ("pre10", "Plano Pré-Pago 10", "10 gerações de jogos", 49.90, None, "pre_pago", 10),
    ]

    for plano in planos_iniciais:
        cursor.execute("""
            INSERT OR IGNORE INTO planos
            (codigo, nome, descricao, valor, validade_dias, tipo, creditos)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, plano)

    conn.commit()
    conn.close()

    print("✅ Tabela 'planos' criada/atualizada com sucesso.")

if __name__ == "__main__":
    criar_tabela_planos()
