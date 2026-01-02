# core/fechamento_lotofacil.py
import random
import sqlite3
from pathlib import Path

DB_PATH = Path("db/loterias.db")


# --------------------------------------------------
# PREÇO DO JOGO (BUSCA NO SQLITE)
# --------------------------------------------------
def obter_valor_jogo_lotofacil(dezenas_por_jogo: int) -> float:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT valor FROM lotofacil_precos WHERE dezenas = ?",
        (dezenas_por_jogo,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise ValueError(
            f"Não há preço cadastrado para Lotofácil com {dezenas_por_jogo} dezenas"
        )

    return float(row[0])


# --------------------------------------------------
# GERAR FECHAMENTO LOTOFÁCIL
# --------------------------------------------------
def gerar_fechamento(
    numeros_base,
    minimo_acertos,
    dezenas_por_jogo,
    orcamento
):
    """
    Gera o fechamento de jogos da Lotofácil usando preços do SQLite.
    """

    if dezenas_por_jogo < 15 or dezenas_por_jogo > 20:
        raise ValueError("Lotofácil permite de 15 a 20 dezenas por jogo")

    preco_jogo = obter_valor_jogo_lotofacil(dezenas_por_jogo)

    if orcamento < preco_jogo:
        raise ValueError(
            f"Orçamento insuficiente. "
            f"Valor do jogo ({dezenas_por_jogo} dezenas): R$ {preco_jogo:.2f}"
        )

    qtd_jogos_max = int(orcamento // preco_jogo)

    jogos = []
    for _ in range(qtd_jogos_max):
        jogo = sorted(random.sample(numeros_base, dezenas_por_jogo))
        jogos.append(jogo)

    estatisticas = {
        "qtd_jogos": len(jogos),
        "minimo_acertos": minimo_acertos,
        "orcamento": orcamento,
        "dezenas_por_jogo": dezenas_por_jogo,
        "valor_por_jogo": preco_jogo
    }

    return {
        "jogos": jogos,
        "estatisticas": estatisticas
    }


# --------------------------------------------------
# HISTÓRICO LOTOFÁCIL
# --------------------------------------------------
def carregar_historico():
    """
    Carrega o histórico de resultados da Lotofácil.
    Retorna lista de sets.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    colunas = ", ".join(f"dezena{i}" for i in range(1, 16))
    cursor.execute(
        f"SELECT {colunas} FROM concursos_lotofacil ORDER BY concurso ASC"
    )
    linhas = cursor.fetchall()
    conn.close()

    return [set(linha) for linha in linhas]


# --------------------------------------------------
# TESTE LOCAL
# --------------------------------------------------
if __name__ == "__main__":
    base = list(range(1, 26))

    resultado = gerar_fechamento(
        numeros_base=base,
        minimo_acertos=11,
        dezenas_por_jogo=15,
        orcamento=100
    )

    print(resultado["estatisticas"])
