import sqlite3
import os

DB_PATH = os.path.join("db", "loterias.db")

def criar_tabela_usuarios():
    """
    Cria a tabela 'usuarios' com todas as colunas necessárias para o bot:
    telegram_id, nome, plano_codigo, pix_codigo, acesso_inicio, acesso_fim,
    status, criado_em.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            nome TEXT,
            plano_codigo TEXT,
            pix_codigo TEXT,
            acesso_inicio DATETIME,
            acesso_fim DATETIME,
            status TEXT DEFAULT 'pendente',
            estado TEXT,
            estado_atualizado_em DATETIME,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plano_codigo) REFERENCES planos(codigo)
        );
    """)

    conn.commit()
    conn.close()
    print("✅ Tabela 'usuarios' criada com sucesso.")

if __name__ == "__main__":
    criar_tabela_usuarios()
