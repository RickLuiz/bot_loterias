import sqlite3
import pandas as pd
from config import DB_PATH


def carregar_historico():
    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query("""
        SELECT dezena1, dezena2, dezena3, dezena4, dezena5,
               dezena6, dezena7, dezena8, dezena9, dezena10,
               dezena11, dezena12, dezena13, dezena14, dezena15
        FROM concursos_lotofacil
        ORDER BY concurso ASC
    """, conn)

    conn.close()

    return [set(row) for _, row in df.iterrows()]


def rodar_backtest(jogos):
    historico = carregar_historico()

    resultado = []

    for idx, jogo in enumerate(jogos, start=1):
        jogo_set = set(jogo)

        contagem = {
            11: 0,
            12: 0,
            13: 0,
            14: 0,
            15: 0
        }

        for concurso in historico:
            acertos = len(jogo_set & concurso)
            if acertos >= 11:
                contagem[acertos] += 1

        resultado.append({
            "jogo": idx,
            **contagem
        })

    return resultado
