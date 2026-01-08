# bot.py
import time
import csv
import sqlite3
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from core.planos import carregar_planos_ativos
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from config import TELEGRAM_TOKEN
from core.fechamento_lotofacil import gerar_fechamento as gerar_fechamento_lotofacil, carregar_historico as carregar_historico_lotofacil
from core.fechamento_megasena import  gerar_fechamento as gerar_fechamento_megasena,  carregar_historico as carregar_historico_megasena
from core.backtest_lotofacil import rodar_backtest
from core.backtest_megasena import rodar_backtest as rodar_backtest_megasena
from fpdf import FPDF


DB_PATH = "db/loterias.db"

# ================= ESTADOS =================
SESSION_TIMEOUT = 300  # 5 minutos (em segundos)

APRESENTACAO = "APRESENTACAO"
CIENCIA_RISCO = "CIENCIA_RISCO"
ESCOLHER_PLANO = "ESCOLHER_PLANO"
GERAR_PIX = "GERAR_PIX"
AGUARDAR_PAGAMENTO = "AGUARDAR_PAGAMENTO"

ESCOLHER_LOTERIA = "ESCOLHER_LOTERIA"
ESCOLHER_BASE = "ESCOLHER_BASE"
BASE_MANUAL = "BASE_MANUAL"
QTD_DEZENAS = "QTD_DEZENAS"
ALVO = "ALVO"
ORCAMENTO = "ORCAMENTO"
CONFIRMAR_ORCAMENTO = "CONFIRMAR_ORCAMENTO"
OPCOES_JOGOS = "OPCOES_JOGOS"


async def callback_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    # Sempre responder o callback para evitar "loading infinito"
    await query.answer(
        "⚠️ Esta ação pertence a uma sessão antiga.\n"
        "Use /start para continuar.",
        show_alert=True
    )




def marcar_atividade(context: ContextTypes.DEFAULT_TYPE):
    context.user_data["_ultima_atividade"] = time.time()


def sessao_expirada(context: ContextTypes.DEFAULT_TYPE) -> bool:
    ultima = context.user_data.get("_ultima_atividade")
    if not ultima:
        return False
    return (time.time() - ultima) > SESSION_TIMEOUT

async def tratar_sessao_expirada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    texto = (
        "⏱️ Sua sessão expirou por inatividade.\n\n"
        "Voltando ao menu principal."
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(texto)
    elif update.message:
        await update.message.reply_text(texto)

    return await menu_loterias(update, context)




def garantir_usuario(telegram_id: int, nome: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO usuarios (telegram_id, nome, status)
        VALUES (?, ?, 'pendente')
    """, (telegram_id, nome))

    conn.commit()
    conn.close()



# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id

    # Garante que o usuário exista no banco
    garantir_usuario(
        telegram_id=telegram_id,
        nome=user.full_name
    )

    # Limpa dados de sessão e marca atividade
    context.user_data.clear()
    marcar_atividade(context)

    # ===============================
    # USUÁRIO COM ACESSO
    # ===============================
    if usuario_tem_acesso(telegram_id):
        # 🔁 SEMPRE reutiliza o mesmo menu
        return await menu_loterias(update, context)

    # ===============================
    # USUÁRIO SEM ACESSO (PRIMEIRO USO)
    # ===============================
    texto = (
        "🎯 *Super Bot FecLoterias*\n\n"
        "Este bot realiza *fechamentos estatísticos* de jogos.\n\n"
        "⚠️ *ATENÇÃO*\n"
        "Não existe garantia de premiação.\n"
        "Trata-se apenas de análise matemática."
    )

    keyboard = [
        [InlineKeyboardButton("Continuar", callback_data="continuar")]
    ]

    if update.message:
        await update.message.reply_text(
            texto,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            texto,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    return APRESENTACAO


def usuario_tem_acesso(telegram_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            status,
            acesso_fim,
            plano_pre,
            creditos
        FROM usuarios
        WHERE telegram_id = ?
    """, (telegram_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return False

    status, acesso_fim, plano_pre, creditos = row

    # 🔒 precisa estar ativo
    if status != "ativo":
        return False

    # ======================================
    # 🟢 PLANO PRÉ-PAGO (POR CRÉDITOS)
    # ======================================
    if plano_pre:
        try:
            return int(creditos or 0) > 0
        except (TypeError, ValueError):
            return False

    # ======================================
    # 🔵 PLANO POR PERÍODO (LÓGICA ORIGINAL)
    # ======================================
    if not acesso_fim:
        return False

    try:
        if datetime.now() > datetime.fromisoformat(acesso_fim):
            return False
    except ValueError:
        return False

    return True

    
# ================= CIÊNCIA DE RISCO =================
async def ciencia_risco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    texto = (
        "📌 *Ciência de Risco*\n\n"
        "Ao continuar, você declara que entende que:\n\n"
        "• Não há garantia de acerto\n"
        "• O bot não promete ganhos\n"
        "• A responsabilidade é exclusivamente do usuário"
    )

    keyboard = [
        [InlineKeyboardButton("Concordo", callback_data="concordo")],
        [InlineKeyboardButton("Cancelar", callback_data="cancelar")]
    ]

    await query.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CIENCIA_RISCO

# ================= PLANOS =================
async def escolher_plano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    planos = carregar_planos_ativos()

    if not planos:
        await query.message.reply_text("❌ Nenhum plano disponível no momento.")
        return ConversationHandler.END

    texto = "💳 *Planos Disponíveis*\n\n"
    keyboard = []

    for plano in planos:
        texto += (
            f"*{plano['nome']}*\n"
            f"• {plano['descricao']}\n"
            f"• Validade: {plano['validade_dias']} dias\n"
            f"• Valor: R$ {plano['valor']:.2f}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"Assinar {plano['nome']}",
                callback_data=f"plano_{plano['codigo']}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        texto,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return ESCOLHER_PLANO


# ================= PIX =================

async def gerar_pix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    codigo_plano = query.data.replace("plano_", "")

    # 🔹 gera um código PIX temporário
    pix_code = f"PIX-{codigo_plano.upper()}-{int(time.time())}"

    agora = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 🔹 garante que o usuário exista
    cursor.execute("""
        INSERT OR IGNORE INTO usuarios (telegram_id, status)
        VALUES (?, 'pendente')
    """, (user_id,))

    # 🔹 vincula plano + PIX (ainda sem liberar acesso)
    cursor.execute("""
        UPDATE usuarios
        SET plano_codigo = ?,
            pix_codigo = ?,
            status = 'pendente',
            acesso_inicio = NULL,
            acesso_fim = NULL
        WHERE telegram_id = ?
    """, (codigo_plano, pix_code, user_id))

    conn.commit()
    conn.close()

    # 🔹 teclado com botão "Já paguei"
    keyboard = [
        [InlineKeyboardButton("✅ Já paguei", callback_data="pago")]
    ]

    await query.message.reply_text(
        f"💸 *Pagamento via PIX*\n\n"
        f"Plano escolhido: `{codigo_plano}`\n"
        f"Código PIX (teste):\n"
        f"`{pix_code}`\n\n"
        "Após pagar, clique em *Já paguei*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

    return AGUARDAR_PAGAMENTO


# ================= CONFIRMA PAGAMENTO =================

async def confirmar_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    agora = datetime.now()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 🔹 busca plano vinculado ao usuário
    cursor.execute("""
        SELECT plano_codigo
        FROM usuarios
        WHERE telegram_id = ?
    """, (user_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        conn.close()
        await query.message.reply_text(
            "⚠️ Nenhum plano encontrado para este usuário."
        )
        return ConversationHandler.END

    codigo_plano = row[0]

    # 🔹 busca dados completos do plano
    cursor.execute("""
        SELECT nome, validade_dias, tipo, creditos
        FROM planos
        WHERE codigo = ? AND ativo = 1
    """, (codigo_plano,))
    plano = cursor.fetchone()

    if not plano:
        conn.close()
        await query.message.reply_text(
            "⚠️ Plano inválido ou inativo."
        )
        return ConversationHandler.END

    nome_plano, validade_dias, tipo_plano, creditos_plano = plano

    # ======================================
    # 🟢 PLANO PRÉ-PAGO (CRÉDITOS)
    # ======================================
    if tipo_plano == "pre_pago":
        cursor.execute("""
           UPDATE usuarios
            SET status = 'ativo',
                plano_tipo = 'pre',
                plano_pre = 1,
                creditos = ?,
                acesso_inicio = NULL,
                acesso_fim = NULL
            WHERE telegram_id = ?

        """, (
            int(creditos_plano or 0),
            user_id
        ))

        conn.commit()
        conn.close()

        await query.message.reply_text(
            f"✅ *Pagamento confirmado!*\n\n"
            f"📦 Plano: *{nome_plano}*\n"
            f"🎟️ Créditos disponíveis: *{creditos_plano}*\n\n"
            "Cada geração de jogos consome 1 crédito.",
            parse_mode="Markdown"
        )

        return await menu_loterias(update, context)

    # ======================================
    # 🔵 PLANO POR PERÍODO (LÓGICA ORIGINAL)
    # ======================================
    acesso_inicio = agora
    acesso_fim = agora + timedelta(days=validade_dias)

    cursor.execute("""
      UPDATE usuarios
        SET status = 'ativo',
            plano_tipo = 'periodo',
            plano_pre = 0,
            creditos = NULL,
            acesso_inicio = ?,
            acesso_fim = ?
        WHERE telegram_id = ?

    """, (
        acesso_inicio.isoformat(),
        acesso_fim.isoformat(),
        user_id
    ))

    conn.commit()
    conn.close()

    await query.message.reply_text(
        f"✅ *Pagamento confirmado!*\n\n"
        f"📦 Plano: *{nome_plano}*\n"
        f"⏳ Acesso válido até: *{acesso_fim.strftime('%d/%m/%Y')}*",
        parse_mode="Markdown"
    )

    return await menu_loterias(update, context)


def consumir_credito(telegram_id: int) -> bool:
    """
    Consome 1 crédito se o usuário for plano pré-pago.
    Retorna:
        True  -> pode continuar (ou não é plano pré)
        False -> plano pré sem créditos (bloquear geração)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT plano_pre, creditos
        FROM usuarios
        WHERE telegram_id = ?
    """, (telegram_id,))

    row = cursor.fetchone()

    # usuário não encontrado → deixa a lógica superior tratar
    if not row:
        conn.close()
        return False

    plano_pre, creditos = row

    # 🔵 não é plano pré → não consome e libera
    if not plano_pre:
        conn.close()
        return True

    creditos = int(creditos or 0)

    # 🔴 plano pré sem crédito → bloqueia
    if creditos <= 0:
        conn.close()
        return False

    # 🟢 consome crédito
    cursor.execute("""
        UPDATE usuarios
        SET creditos = creditos - 1
        WHERE telegram_id = ?
    """, (telegram_id,))

    conn.commit()
    conn.close()
    return True



# ================= MENU LOTERIAS =================
async def menu_loterias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🔎 identifica o usuário corretamente
    if update.effective_user:
        user_id = update.effective_user.id
    else:
        user_id = update.callback_query.from_user.id

    # 🔎 busca info do plano
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT plano_pre, creditos, acesso_fim
        FROM usuarios
        WHERE telegram_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    info_plano = ""

    if row:
        plano_pre, creditos, acesso_fim = row

        # 🟢 PLANO PRÉ-PAGO
        if plano_pre:
            info_plano = f"\n🎟️ *Créditos disponíveis:* {int(creditos or 0)}\n"

        # 🔵 PLANO POR PERÍODO
        elif acesso_fim:
            try:
                vencimento = datetime.fromisoformat(acesso_fim).strftime("%d/%m/%Y")
                info_plano = f"\n⏳ *Plano válido até:* {vencimento}\n"
            except ValueError:
                pass

    # ===============================
    # 📋 TEXTO PRINCIPAL
    # ===============================
    texto = (
        "🎯 *Super Bot FecLoterias*\n\n"
        "Escolha a loteria para realizar o fechamento:"
        f"{info_plano}"
    )

    # ===============================
    # 🎛️ TECLADO
    # ===============================
    keyboard = [
        [
            InlineKeyboardButton("Lotofácil", callback_data="lotofacil"),
            InlineKeyboardButton("Mega-Sena", callback_data="megasena")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # ===============================
    # 📤 ENVIO DA MENSAGEM
    # ===============================
    if update.message:
        await update.message.reply_text(
            texto,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            texto,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    return ESCOLHER_LOTERIA

async def escolher_loteria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if sessao_expirada(context):
        return await tratar_sessao_expirada(update, context)

    marcar_atividade(context)

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    loteria = query.data

    if not usuario_tem_acesso(user_id):
        await query.message.reply_text(
            "🔒 Seu acesso não está ativo ou expirou.\n\n"
            "Assine um plano para continuar."
        )
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["loteria"] = loteria
    marcar_atividade(context)

    keyboard = [
        [
            InlineKeyboardButton("✍️ Dezenas manuais", callback_data="manual"),
            InlineKeyboardButton("⚙️ Automático", callback_data="historico")
        ],
        [InlineKeyboardButton("🔄 Reiniciar", callback_data="restart")]
    ]

    await query.message.reply_text(
        "Escolha como deseja definir as dezenas para gerar os jogos:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ESCOLHER_BASE



# --- ESCOLHER BASE ---
async def escolher_base(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    loteria = context.user_data.get("loteria")

    # 🔒 segurança de fluxo
    if not loteria:
        return await menu_loterias(update, context)

    # ===============================
    # ✍️ DEZENAS MANUAIS
    # ===============================
    if query.data == "manual":
        # ✅ registra tipo corretamente para logs
        context.user_data["tipo_base"] = "manual"

        dezenas = list(range(1, 26)) if loteria == "lotofacil" else list(range(1, 61))

        context.user_data["numeros_base"] = []
        context.user_data["numeros_base_selecionaveis"] = dezenas

        keyboard = []
        linha = []
        colunas = 5 if loteria == "lotofacil" else 6

        for d in dezenas:
            linha.append(
                InlineKeyboardButton(str(d), callback_data=f"dezena_{d}")
            )
            if len(linha) == colunas:
                keyboard.append(linha)
                linha = []

        if linha:
            keyboard.append(linha)

        keyboard.append(
            [InlineKeyboardButton("Concluir", callback_data="concluir")]
        )

        await query.message.reply_text(
            "Selecione as dezenas clicando nos botões:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return BASE_MANUAL

    # ===============================
    # ⚙️ AUTOMÁTICO (HISTÓRICO)
    # ===============================
    elif query.data == "historico":
        # ✅ registra tipo corretamente para logs
        context.user_data["tipo_base"] = "automatico"

        if loteria == "lotofacil":
            historico = carregar_historico_lotofacil()
            base = sorted(
                {
                    int(n)
                    for jogo in historico
                    for n in jogo
                    if str(n).isdigit()
                }
            )
            opcoes = list(range(15, 21))
        else:
            historico = carregar_historico_megasena()
            base = sorted(
                {
                    int(n)
                    for n in historico.values.flatten()
                    if pd.notna(n)
                }
            )
            opcoes = list(range(6, 11))

        if not base:
            raise ValueError("Base histórica vazia ou inválida.")

        context.user_data["numeros_base"] = base

        keyboard = [
            [InlineKeyboardButton(str(d), callback_data=f"qtd_{d}")]
            for d in opcoes
        ]

        await query.message.reply_text(
            f"Base histórica selecionada: {', '.join(map(str, base))}\n"
            f"Selecione a quantidade de dezenas por jogo:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return QTD_DEZENAS

    # ===============================
    # 🔄 RESTART
    # ===============================
    elif query.data == "restart":
        context.user_data.clear()
        return await menu_loterias(update, context)



# --- BASE MANUAL COM BOTÕES ---
async def base_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    dados = context.user_data  # 🧠 estado da conversa

    if "numeros_base" not in dados or "loteria" not in dados:
        await query.message.reply_text(
            "⚠️ Sessão expirada. Vamos começar novamente."
        )
        return ConversationHandler.END

    # ✅ clique em concluir
    if query.data == "concluir":
        qtd = len(dados["numeros_base"])
        loteria = dados["loteria"]

        min_dezenas = 15 if loteria == "lotofacil" else 6
        max_dezenas = 25 if loteria == "lotofacil" else 60

        if qtd < min_dezenas:
            await query.message.reply_text(
                f"⚠️ Você selecionou {qtd} dezenas.\n"
                f"Mínimo permitido: {min_dezenas}."
            )
            return BASE_MANUAL

        if qtd > max_dezenas:
            await query.message.reply_text(
                f"⚠️ Você selecionou {qtd} dezenas.\n"
                f"Máximo permitido: {max_dezenas}."
            )
            return BASE_MANUAL

        # opções de dezenas por jogo
        opcoes = list(range(15, 21)) if loteria == "lotofacil" else list(range(6, 11))
        keyboard = [
            [InlineKeyboardButton(str(d), callback_data=f"qtd_{d}")]
            for d in opcoes
        ]

        await query.message.reply_text(
            f"✅ Base definida:\n{', '.join(map(str, sorted(dados['numeros_base'])))}\n\n"
            "Selecione a quantidade de dezenas por jogo:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return QTD_DEZENAS

    # ✅ clique em uma dezena
    if query.data.startswith("dezena_"):
        valor = query.data.split("_", 1)[1]

        if not valor.isdigit():
            return BASE_MANUAL

        dezena = int(valor)

        if dezena in dados["numeros_base"]:
            dados["numeros_base"].remove(dezena)
        else:
            dados["numeros_base"].append(dezena)

        # 🔄 reconstrói teclado com marcação
        loteria = dados["loteria"]
        dezenas = dados["numeros_base_selecionaveis"]

        keyboard = []
        linha = []
        colunas = 5 if loteria == "lotofacil" else 6

        for d in dezenas:
            texto = f"✅{d}" if d in dados["numeros_base"] else str(d)
            linha.append(InlineKeyboardButton(texto, callback_data=f"dezena_{d}"))

            if len(linha) == colunas:
                keyboard.append(linha)
                linha = []

        if linha:
            keyboard.append(linha)

        keyboard.append(
            [InlineKeyboardButton("Concluir", callback_data="concluir")]
        )

        await query.message.edit_text(
            "Selecione as dezenas clicando nos botões:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return BASE_MANUAL


# --- QTD_DEZENAS atualizado ---
async def qtd_dezenas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    loteria = user_data.get("loteria")

    if not loteria:
        await update.message.reply_text(
            "⚠️ Fluxo inválido. Use /start para reiniciar."
        )
        return ConversationHandler.END

    # Opções de dezenas por jogo
    opcoes = list(range(15, 21)) if loteria == "lotofacil" else list(range(6, 11))

    # Cria teclado (uma coluna por botão)
    keyboard = [[InlineKeyboardButton(str(d), callback_data=f"qtd_{d}")] for d in opcoes]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Selecione a quantidade de dezenas por jogo:",
        reply_markup=reply_markup
    )
    return QTD_DEZENAS




# --- SELECIONAR QTD_DEZENAS usando apenas context.user_data ---
async def selecionar_qtd_dezenas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data = context.user_data
    loteria = user_data.get("loteria")

    if not loteria:
        await query.message.reply_text(
            "⚠️ Fluxo inválido. Use /start para reiniciar."
        )
        return ConversationHandler.END

    if query.data.startswith("qtd_"):
        qtd = int(query.data.split("_")[1])
        user_data["dezenas_por_jogo"] = qtd

        # opções de alvo mínimo
        opcoes_alvo = [11, 12, 13, 14] if loteria == "lotofacil" else [4, 5]
        keyboard = [[InlineKeyboardButton(str(a), callback_data=f"alvo_{a}")] for a in opcoes_alvo]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            f"✅ Quantidade de dezenas por jogo definida: {qtd}\n\n"
            "Selecione o alvo mínimo de acertos:",
            reply_markup=reply_markup
        )
        return ALVO


# --- ALVO --- 
async def alvo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    loteria = user_data.get("loteria")

    if not loteria:
        await update.message.reply_text(
            "⚠️ Fluxo inválido. Use /start para reiniciar."
        )
        return ConversationHandler.END

    # ✅ se veio pelo callback (botão)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data.startswith("alvo_"):
            alvo = int(query.data.split("_")[1])
            user_data["minimo_acertos"] = alvo
            await query.message.edit_text(
                f"✅ Alvo mínimo de acertos definido: {alvo}\n\n"
                "Digite agora o orçamento disponível (R$):"
            )
            return ORCAMENTO

    # ✅ se veio pelo texto digitado
    elif update.message:
        try:
            alvo = int(update.message.text)
            user_data["minimo_acertos"] = alvo
            await update.message.reply_text(
                "Digite o orçamento disponível (R$):"
            )
            return ORCAMENTO
        except ValueError:
            await update.message.reply_text(
                "Valor inválido. Digite novamente o alvo mínimo de acertos."
            )
            return ALVO

    

# --- SELECIONAR ALVO ---
async def selecionar_alvo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data = context.user_data
    loteria = user_data.get("loteria")

    if not loteria:
        await query.message.reply_text(
            "⚠️ Fluxo inválido. Use /start para reiniciar."
        )
        return ConversationHandler.END

    if query.data.startswith("alvo_"):
        alvo = int(query.data.split("_")[1])
        user_data["minimo_acertos"] = alvo

        await query.message.edit_text(
            f"✅ Alvo mínimo de acertos definido: {alvo}\n\n"
            "Digite agora o orçamento disponível (R$):"
        )
        return ORCAMENTO



# --- ORÇAMENTO ---
async def orcamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    loteria = user_data.get("loteria")

    if not loteria:
        await update.message.reply_text(
            "⚠️ Fluxo inválido. Use /start para reiniciar."
        )
        return ConversationHandler.END

    try:
        # substitui vírgula por ponto e converte para float
        orc = float(update.message.text.replace(",", "."))
        user_data["orcamento"] = orc

        numeros_str = ", ".join(map(str, user_data.get("numeros_base", [])))
        msg_confirma = (
            "🔎 Confirme os parâmetros para gerar a análise:\n\n"
            f"Loteria            : {loteria.capitalize()}\n"
            f"Números base       : {numeros_str}\n"
            f"Dezenas por jogo   : {user_data.get('dezenas_por_jogo')}\n"
            f"Mínimo de acertos  : {user_data.get('minimo_acertos')}\n"
            f"Orçamento (R$)     : {user_data.get('orcamento'):.2f}\n\n"
            "Deseja confirmar?"
        )

        keyboard = [
            [InlineKeyboardButton("✅ Confirmar", callback_data="confirmar")],
            [InlineKeyboardButton("🔄 Reiniciar", callback_data="restart")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(msg_confirma, reply_markup=reply_markup)
        return CONFIRMAR_ORCAMENTO

    except ValueError:
        await update.message.reply_text(
            "Valor inválido. Digite novamente o orçamento em R$."
        )
        return ORCAMENTO


# --- CONFIRMAR ORCAMENTO ---
async def confirmar_orcamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    loteria = user_data.get("loteria")

    if not loteria:
        await query.message.reply_text(
            "⚠️ Fluxo inválido. Use /start para reiniciar."
        )
        return ConversationHandler.END

    if query.data == "confirmar":

        user_id = query.from_user.id

        # 🔒 valida e consome crédito (plano pré)
        if not consumir_credito(user_id):
            await query.message.reply_text(
                "❌ *Créditos insuficientes*\n\n"
                "Seu plano pré-pago não possui créditos disponíveis.\n"
                "Adquira mais créditos para continuar.",
                parse_mode="Markdown"
            )
            return OPCOES_JOGOS

        try:
            # ===============================
            # 🔒 SANITIZAÇÃO DOS NÚMEROS BASE
            # ===============================
            numeros_base = user_data.get("numeros_base", [])

            numeros_base_limpos = []
            for n in numeros_base:
                if isinstance(n, int):
                    numeros_base_limpos.append(n)
                elif isinstance(n, str) and n.isdigit():
                    numeros_base_limpos.append(int(n))

            numeros_base_limpos = sorted(set(numeros_base_limpos))

            if not numeros_base_limpos:
                raise ValueError("Base de números inválida ou vazia.")

            # valida range por loteria
            if loteria == "lotofacil":
                numeros_base_limpos = [n for n in numeros_base_limpos if 1 <= n <= 25]
            else:
                numeros_base_limpos = [n for n in numeros_base_limpos if 1 <= n <= 60]

            if len(numeros_base_limpos) < user_data.get("dezenas_por_jogo", 0):
                raise ValueError("Quantidade de dezenas base insuficiente após validação.")

            user_data["numeros_base"] = numeros_base_limpos

            # ===============================
            # 🎯 GERA FECHAMENTO
            # ===============================
            if loteria == "lotofacil":
                resultado = gerar_fechamento_lotofacil(
                    numeros_base=numeros_base_limpos,
                    minimo_acertos=user_data["minimo_acertos"],
                    dezenas_por_jogo=user_data["dezenas_por_jogo"],
                    orcamento=user_data["orcamento"],
                )
            else:
                resultado = gerar_fechamento_megasena(
                    numeros_base=numeros_base_limpos,
                    minimo_acertos=user_data["minimo_acertos"],
                    dezenas_por_jogo=user_data["dezenas_por_jogo"],
                    orcamento=user_data["orcamento"],
                )

            user_data["resultado"] = resultado
            user_data["backtest_executado"] = False

            # ===============================
            # 📊 BACKTEST AUTOMÁTICO (1x)
            # ===============================
            if loteria == "lotofacil":
                user_data["backtest"] = rodar_backtest(resultado["jogos"])
            else:
                user_data["backtest"] = rodar_backtest_megasena(resultado["jogos"])

            # ===============================
            # 🔎 DADOS PARA LOG
            # ===============================
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT creditos, plano_codigo
                FROM usuarios
                WHERE telegram_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            conn.close()

            creditos_restantes = row[0] if row else None
            plano_codigo = row[1] if row else None

            # 🔹 tipo de dezenas (manual / automatico)
            tipo_dezenas = "manual" if user_data.get("tipo_base") == "manual" else "automatico"


            # ===============================
            # 📝 REGISTRA LOG DA TRANSAÇÃO
            # ===============================
            id_log = registrar_log(
                loteria=loteria,
                id_usuario=user_id,
                id_plano=plano_codigo,
                creditos=creditos_restantes,
                tipo_dezenas=tipo_dezenas,
                dezenas_selecionadas=numeros_base_limpos,
                qtd_dezenas=user_data["dezenas_por_jogo"],
                alvo=user_data["minimo_acertos"],
                orcamento=user_data["orcamento"],
                qtd_jogos_gerados=resultado["estatisticas"]["qtd_jogos"],
            )

            context.user_data["id_log"] = id_log  # 🔥 ESSENCIAL


            # ===============================
            # 📊 MENSAGEM AO USUÁRIO
            # ===============================
            msg = (
                f"✅ *Análise concluída!*\n\n"
                f"🎯 Loteria: {loteria.capitalize()}\n"
                f"📊 Jogos gerados: {resultado['estatisticas']['qtd_jogos']}\n"
                f"🎲 Dezenas por jogo: {user_data['dezenas_por_jogo']}\n"
                f"🏆 Mínimo garantido: {resultado['estatisticas']['minimo_acertos']}\n"
                f"💰 Orçamento usado: R$ {resultado['estatisticas']['orcamento']:.2f}\n\n"
                "📁 Use as opções abaixo para baixar os jogos completos."
            )

            keyboard = [
                [InlineKeyboardButton("📊 Rodar Backtest", callback_data="backtest")],
                [
                    InlineKeyboardButton("📄 Exportar Jogos (CSV)", callback_data="csv_jogos"),
                    InlineKeyboardButton("📕 Exportar Jogos (PDF)", callback_data="pdf_jogos")
                ],
                [InlineKeyboardButton("🔄 Reiniciar", callback_data="restart")]
            ]

            await query.message.reply_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

            return OPCOES_JOGOS

        except ValueError as e:
            await query.message.reply_text(
                f"⚠️ {e}\n💰 Por favor, informe um novo valor de orçamento (R$):"
            )
            return ORCAMENTO

    elif query.data == "restart":
        user_data.clear()
        return await menu_loterias(update, context)

    
def registrar_log(
    *,
    loteria: str,
    id_usuario: int,
    id_plano: str | None,
    creditos: int | None,
    tipo_dezenas: str,
    dezenas_selecionadas: list[int],
    qtd_dezenas: int,
    alvo: int,
    orcamento: float,
    qtd_jogos_gerados: int,
    csv_jogos: bool = False,
    pdf_jogos: bool = False,
    backtest: bool = False,
    csv_backtest: bool = False
) -> int:
    """
    Registra uma transação completa na tabela logs e
    retorna o id_log gerado.
    """

    # ===============================
    # 🔒 SANITIZAÇÃO DEFENSIVA
    # ===============================
    tipo_dezenas_final = (
        tipo_dezenas
        if tipo_dezenas in ("manual", "automatico")
        else "automatico"
    )

    dezenas_str = ",".join(
        str(d) for d in (dezenas_selecionadas or []) if isinstance(d, int)
    )

    creditos_final = int(creditos) if creditos is not None else None

    # ===============================
    # 📝 INSERT DO LOG
    # ===============================
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO logs (
            data_transacao,
            loteria,
            id_usuario,
            id_plano,
            creditos,
            tipo_dezenas,
            dezenas_selecionadas,
            qtd_dezenas,
            alvo,
            orcamento,
            qtd_jogos_gerados,
            csv_jogos,
            pdf_jogos,
            backtest,
            csv_backtest
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        loteria,
        id_usuario,
        id_plano,
        creditos_final,
        tipo_dezenas_final,
        dezenas_str,
        int(qtd_dezenas),
        int(alvo),
        float(orcamento),
        int(qtd_jogos_gerados),
        int(bool(csv_jogos)),
        int(bool(pdf_jogos)),
        int(bool(backtest)),
        int(bool(csv_backtest)),
    ))

    id_log = cursor.lastrowid  # 🔑 ID DA TRANSAÇÃO

    conn.commit()
    conn.close()

    return id_log


def montar_keyboard_opcoes(user_data, plano_pre=False):
    botoes = []

    # 🔹 Backtest só aparece se:
    # - não for plano pré
    # - ou for plano pré e ainda não executou
    if not plano_pre or not user_data.get("backtest_executado"):
        botoes.append(
            [InlineKeyboardButton("📊 Rodar Backtest", callback_data="backtest")]
        )

    botoes.append(
        [InlineKeyboardButton("📄 Exportar Jogos (CSV)", callback_data="csv_jogos")]
    )

    botoes.append(
        [InlineKeyboardButton("📄 Exportar Jogos (PDF)", callback_data="pdf_jogos")]
    )

    botoes.append(
        [InlineKeyboardButton("🔄 Reiniciar", callback_data="restart")]
    )

    return InlineKeyboardMarkup(botoes)


def atualizar_log(id_log: int, campo: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE logs SET {campo} = 1 WHERE id_log = ?",
        (id_log,)
    )
    conn.commit()
    conn.close()



# --- OPÇÕES JOGOS ---
async def opcoes_jogos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    resultado = user_data.get("resultado")
    loteria = user_data.get("loteria")
    id_log = user_data.get("id_log")  # 🔑 LOG ATUAL

    if not resultado or not loteria or not id_log:
        await query.message.reply_text(
            "⚠️ Fluxo inválido. Use /start para reiniciar."
        )
        return ConversationHandler.END

    # ---------------- BACKTEST ----------------
    if query.data == "backtest":
        user_id = query.from_user.id

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT plano_pre FROM usuarios WHERE telegram_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()

        plano_pre = bool(row and row[0] == 1)

        if plano_pre and user_data.get("backtest_executado"):
            await query.message.reply_text(
                "⚠️ No plano pré-pago o backtest pode ser executado apenas uma vez por geração."
            )
            return OPCOES_JOGOS

        if loteria == "lotofacil":
            bt_result = rodar_backtest(resultado["jogos"])
            pontos_range = range(11, 16)
        else:
            bt_result = rodar_backtest_megasena(resultado["jogos"])
            pontos_range = range(4, 7)

        user_data["backtest"] = bt_result
        user_data["backtest_executado"] = True

        # ✅ LOG: backtest executado
        atualizar_log(id_log, "backtest")

        resumo = {i: sum(r[i] for r in bt_result) for i in pontos_range}
        melhor_jogo = max(bt_result, key=lambda x: sum(x[i] for i in pontos_range))

        texto_resumo = (
            f"📊 *Backtest concluído ({loteria.upper()})*\n\n"
            f"Qtd de jogos       : {len(bt_result)}\n"
            f"Dezenas por jogo   : {user_data['dezenas_por_jogo']}\n\n"
        )

        for i in pontos_range:
            texto_resumo += f"{i} pontos : {resumo[i]}\n"

        texto_resumo += (
            "\n🏆 *Melhor jogo*\n"
            f"Jogo : {melhor_jogo['jogo']}\n"
        )

        keyboard = [
            [
                InlineKeyboardButton("📄 Exportar Backtest (CSV)", callback_data="csv_backtest"),
                InlineKeyboardButton("🔄 Reiniciar", callback_data="restart"),
            ]
        ]

        await query.message.reply_text(
            texto_resumo,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        return OPCOES_JOGOS

    # ---------------- EXPORTAR JOGOS CSV ----------------
    elif query.data == "csv_jogos":
        nome_arquivo = f"jogos_{loteria}.csv"

        with open(nome_arquivo, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(
                ["Jogo"] + [f"D{i+1}" for i in range(user_data["dezenas_por_jogo"])]
            )
            for idx, jogo in enumerate(resultado["jogos"], start=1):
                writer.writerow([idx] + list(jogo))

        with open(nome_arquivo, "rb") as f:
            await query.message.reply_document(document=f, filename=nome_arquivo)

        # ✅ LOG
        atualizar_log(id_log, "csv_jogos")

        return OPCOES_JOGOS

    # ---------------- EXPORTAR BACKTEST CSV ----------------
    elif query.data == "csv_backtest":
        backtest = user_data.get("backtest")
        if not backtest:
            await query.message.reply_text("❌ Execute o backtest antes de exportar.")
            return OPCOES_JOGOS

        nome_arquivo = f"backtest_{loteria}.csv"
        pontos_range = range(11, 16) if loteria == "lotofacil" else range(4, 7)

        with open(nome_arquivo, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Jogo"] + [f"{i}_pontos" for i in pontos_range])
            for r in backtest:
                writer.writerow([r["jogo"]] + [r[i] for i in pontos_range])

        with open(nome_arquivo, "rb") as f:
            await query.message.reply_document(document=f, filename=nome_arquivo)

        # ✅ LOG
        atualizar_log(id_log, "csv_backtest")

        return OPCOES_JOGOS

    # ---------------- EXPORTAR PDF ----------------
    elif query.data == "pdf_jogos":
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)

        pdf.cell(0, 10, f"Jogos - {loteria.upper()}", ln=1, align="C")
        pdf.ln(4)

        for idx, jogo in enumerate(resultado["jogos"], 1):
            pdf.multi_cell(0, 8, f"Jogo {idx}: {', '.join(map(str, jogo))}")

        bio = BytesIO(pdf.output(dest="S").encode("latin1"))

        await query.message.reply_document(
            document=bio,
            filename=f"jogos_{loteria}.pdf"
        )

        # ✅ LOG
        atualizar_log(id_log, "pdf_jogos")

        return OPCOES_JOGOS

    # ---------------- RESTART ----------------
    elif query.data == "restart":
        user_data.clear()
        return await menu_loterias(update, context)






# --- CANCEL ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operação cancelada.")
    return ConversationHandler.END


# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            APRESENTACAO: [CallbackQueryHandler(ciencia_risco, pattern="continuar")],
            CIENCIA_RISCO: [CallbackQueryHandler(escolher_plano, pattern="concordo")],
            ESCOLHER_PLANO: [CallbackQueryHandler(gerar_pix, pattern="plano_")],
            AGUARDAR_PAGAMENTO: [CallbackQueryHandler(confirmar_pagamento, pattern="pago")],

            ESCOLHER_LOTERIA: [CallbackQueryHandler(escolher_loteria)],
            ESCOLHER_BASE: [CallbackQueryHandler(escolher_base)],
            BASE_MANUAL: [CallbackQueryHandler(base_manual)],
            QTD_DEZENAS: [CallbackQueryHandler(selecionar_qtd_dezenas)],
            ALVO: [CallbackQueryHandler(selecionar_alvo)],
            ORCAMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, orcamento)],
            CONFIRMAR_ORCAMENTO: [CallbackQueryHandler(confirmar_orcamento)],
            OPCOES_JOGOS: [CallbackQueryHandler(opcoes_jogos)]
        },
        fallbacks=[]
    )

    # 1️⃣ registra o ConversationHandler
    app.add_handler(conv_handler)

    # 2️⃣ fallback global para callbacks órfãos (NÍVEL 2)
    app.add_handler(CallbackQueryHandler(callback_fallback))

    print("🤖 Bot rodando...")
    app.run_polling()

