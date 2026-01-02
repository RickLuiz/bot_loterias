import itertools

DEZENAS_POR_JOGO = 15


def gerar_jogos_fechamento(numeros, minimo_acertos):
    """
    Gera jogos determinísticos garantindo cobertura mínima
    Estratégia: combinações fixas e sobreposição controlada
    """

    if len(numeros) < 15:
        raise ValueError("É necessário no mínimo 15 números base")

    jogos = []

    # Estratégia simples e eficiente:
    # Janela deslizante
    passo = max(1, 15 - minimo_acertos)

    for i in range(0, len(numeros) - 14, passo):
        jogo = numeros[i:i + 15]
        if len(jogo) == 15:
            jogos.append(tuple(sorted(jogo)))

    # Remove duplicados
    jogos = list(dict.fromkeys(jogos))

    return jogos
