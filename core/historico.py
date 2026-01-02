# core/historico.py
import sqlite3
from pathlib import Path

DB_PATH = Path("db/lotofacil.db")

def carregar_historico():
    """Retorna todas as dezenas da Lotofácil como lista de sets"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT dezena1, dezena2, dezena3, dezena4, dezena5, dezena6, dezena7, dezena8, dezena9, "
        "dezena10, dezena11, dezena12, dezena13, dezena14, dezena15 FROM concursos ORDER BY concurso ASC"
    )
    linhas = cursor.fetchall()
    conn.close()

    # Retorna lista de sets
    return [set(linha) for linha in linhas]
