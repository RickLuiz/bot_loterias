import random
import pandas as pd
import sqlite3
import os

DB_PATH = os.path.join("db", "loterias.db")

def obter_valor_jogo_megasena(dezenas_por_jogo: int) -> float:
    """Busca o valor do jogo da Mega-Sena no SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT valor FROM megasena_precos WHERE dezenas = ?",
        (dezenas_por_jogo,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise ValueError(
            f"Não há preço cadastrado para Mega-Sena com {dezenas_por_jogo} dezenas"
        )

    return float(row[0])


def carregar_historico():
    """Carrega o histórico de concursos da Mega-Sena do SQLite."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Banco não encontrado: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM concursos_megasena ORDER BY concurso ASC", conn)
    conn.close()

    # Mega-Sena: sempre 6 dezenas
    colunas = [f"dezena{i}" for i in range(1, 7)]
    df = df[colunas].copy()
    df.columns = [f"D{i}" for i in range(1, 7)]
    return df

def jogo_valido(jogo):
    # 🔹 Garante que tudo seja int
    jogo = [int(n) for n in jogo]

    pares = sum(1 for n in jogo if n % 2 == 0)
    impares = len(jogo) - pares

    return 2 <= pares <= 4


def gerar_fechamento(numeros_base, minimo_acertos=4, dezenas_por_jogo=6, orcamento=None):

    # 🔒 SANITIZA A BASE (REMOVE 'D', TEXTOS, ETC)
    numeros_base = [
        int(n) for n in numeros_base
        if str(n).isdigit() and 1 <= int(n) <= 60
    ]

    df = carregar_historico()
    numeros = df.values.flatten()
    freq_abs = pd.Series(numeros).value_counts().sort_index()

    if len(numeros_base) < dezenas_por_jogo:
        numeros_base = (
            freq_abs.sort_values(ascending=False)
            .head(dezenas_por_jogo)
            .index.tolist()
        )

    # 🔥 BUSCA VALOR NO SQLITE
    VALOR_JOGO = obter_valor_jogo_megasena(dezenas_por_jogo)

    qtd_jogos = int(orcamento // VALOR_JOGO) if orcamento else 3

    jogos = set()
    tentativas = 0
    while len(jogos) < qtd_jogos:
        jogo = sorted(random.sample(numeros_base, dezenas_por_jogo))
        if jogo_valido(jogo):
            jogos.add(tuple(jogo))

        tentativas += 1
        if tentativas > 500_000:
            break

    jogos = list(jogos)

    estatisticas = {
        "qtd_jogos": len(jogos),
        "dezenas_por_jogo": dezenas_por_jogo,
        "minimo_acertos": minimo_acertos,
        "orcamento": orcamento,
        "valor_por_jogo": VALOR_JOGO
    }

    return {"jogos": jogos, "estatisticas": estatisticas}
