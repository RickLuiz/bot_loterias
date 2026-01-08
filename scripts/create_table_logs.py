import sqlite3
import os

DB_DIR = "db"
DB_PATH = os.path.join(DB_DIR, "loterias.db")

def criar_tabela_logs():
    os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id_log INTEGER PRIMARY KEY AUTOINCREMENT,

            data_transacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            loteria TEXT NOT NULL,

            id_usuario INTEGER NOT NULL,
            id_plano TEXT,

            creditos INTEGER,

            tipo_dezenas TEXT CHECK(tipo_dezenas IN ('manual', 'automatico')),

            dezenas_selecionadas TEXT,

            qtd_dezenas INTEGER,
            alvo INTEGER,
            orcamento REAL,
            qtd_jogos_gerados INTEGER,

            csv_jogos INTEGER DEFAULT 0,
            pdf_jogos INTEGER DEFAULT 0,
            backtest INTEGER DEFAULT 0,
            csv_backtest INTEGER DEFAULT 0,

            FOREIGN KEY (id_usuario) REFERENCES usuarios(telegram_id),
            FOREIGN KEY (id_plano) REFERENCES planos(codigo)
        );
    """)

    conn.commit()
    conn.close()

    print("✅ Tabela 'logs' criada com sucesso.")


if __name__ == "__main__":
    criar_tabela_logs()
