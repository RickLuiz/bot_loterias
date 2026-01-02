import sqlite3
from config import DB_PATH
import pandas as pd
import os

DB_PATH = os.path.join("db", "loterias.db")

def carregar_historico():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT dezena1, dezena2, dezena3, dezena4, dezena5, dezena6 FROM concursos_megasena ORDER BY concurso ASC", conn)
    conn.close()
    return [set(row) for _, row in df.iterrows()]

def rodar_backtest(jogos):
    historico = carregar_historico()
    resultado = []
    for idx, jogo in enumerate(jogos, start=1):
        jogo_set = set(jogo)
        contagem = {4: 0, 5: 0, 6: 0}  # Quadras, Quinas, Sena
        for concurso in historico:
            acertos = len(jogo_set & concurso)
            if acertos >= 4:
                contagem[acertos] += 1
        resultado.append({"jogo": idx, **contagem})
    return resultado
