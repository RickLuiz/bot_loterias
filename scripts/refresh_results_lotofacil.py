import requests
import sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Caminho do DB
DB_PATH = Path("db/loterias.db")
DB_PATH.parent.mkdir(exist_ok=True)

# Conectar e criar tabela se não existir
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS concursos_lotofacil (
    concurso INTEGER PRIMARY KEY,
    data TEXT,
    dezena1 INTEGER,
    dezena2 INTEGER,
    dezena3 INTEGER,
    dezena4 INTEGER,
    dezena5 INTEGER,
    dezena6 INTEGER,
    dezena7 INTEGER,
    dezena8 INTEGER,
    dezena9 INTEGER,
    dezena10 INTEGER,
    dezena11 INTEGER,
    dezena12 INTEGER,
    dezena13 INTEGER,
    dezena14 INTEGER,
    dezena15 INTEGER
)
""")
conn.commit()

# Último concurso salvo
cursor.execute("SELECT COALESCE(MAX(concurso), 0) FROM concursos_lotofacil")
ultimo_salvo = cursor.fetchone()[0]
print("Último concurso salvo:", ultimo_salvo)

# Último concurso da API
API_ULTIMO = "https://api.guidi.dev.br/loteria/lotofacil/ultimo"
resp = requests.get(API_ULTIMO)
resp.raise_for_status()
ultimo_json = resp.json()
ultimo_api = ultimo_json.get("numero")
print("Último concurso na API:", ultimo_api)

# Função para baixar um concurso
def baixar_concurso(concurso):
    try:
        url = f"https://api.guidi.dev.br/loteria/lotofacil/{concurso}"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        dezenas = list(map(int, data.get("listaDezenas", [])))
        if len(dezenas) != 15:
            print(f"Concurso {concurso} pulado: número de dezenas incorreto.")
            return None
        print(f"Concurso {concurso} baixado.")
        return (concurso, data.get("dataApuracao"), *dezenas)
    except Exception as e:
        print(f"Erro no concurso {concurso}: {e}")
        return None
    
def carregar_historico():
    """Retorna todas as dezenas da Lotofácil como lista de sets"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT dezena1, dezena2, dezena3, dezena4, dezena5, dezena6, dezena7, dezena8, dezena9, "
        "dezena10, dezena11, dezena12, dezena13, dezena14, dezena15 FROM concursos_lotofacil ORDER BY concurso ASC"
    )
    linhas = cursor.fetchall()
    conn.close()

    # Retorna lista de sets
    return [set(linha) for linha in linhas]    

# Baixar todos os concursos novos em paralelo
novos_concursos = []
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(baixar_concurso, c): c for c in range(ultimo_salvo + 1, ultimo_api + 1)}
    for future in as_completed(futures):
        resultado = future.result()
        if resultado:
            novos_concursos.append(resultado)

# Inserir todos de uma vez no SQLite
if novos_concursos:
    cursor.executemany("""
    INSERT OR IGNORE INTO concursos_lotofacil
    (concurso, data, dezena1, dezena2, dezena3, dezena4, dezena5,
     dezena6, dezena7, dezena8, dezena9, dezena10,
     dezena11, dezena12, dezena13, dezena14, dezena15)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, novos_concursos)
    conn.commit()
    print(f"{len(novos_concursos)} concursos inseridos de uma vez!")

conn.close()
print("Ingestão completa!")
