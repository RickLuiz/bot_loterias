# webhook.py
from fastapi import FastAPI, Request
import sqlite3
import mercadopago
from datetime import datetime, timedelta
from config import MP_ACCESS_TOKEN

app = FastAPI()
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
DB_PATH = "db/loterias.db"

@app.post("/webhook/mercadopago")
async def webhook_mp(request: Request):
    data = await request.json()

    if data.get("type") != "payment":
        return {"status": "ignored"}

    payment_id = data["data"]["id"]
    payment = sdk.payment().get(payment_id)["response"]

    if payment["status"] != "approved":
        return {"status": "pending"}

    user_id, codigo_plano = payment["external_reference"].split("|")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT validade_dias, tipo, creditos
        FROM planos WHERE codigo = ?
    """, (codigo_plano,))
    plano = cursor.fetchone()

    agora = datetime.now()

    if plano[1] == "pre_pago":
        cursor.execute("""
            UPDATE usuarios
            SET status='ativo',
                plano_pre=1,
                plano_tipo='pre',
                creditos=?,
                acesso_inicio=NULL,
                acesso_fim=NULL
            WHERE telegram_id=?
        """, (plano[2], user_id))
    else:
        acesso_fim = agora + timedelta(days=plano[0])
        cursor.execute("""
            UPDATE usuarios
            SET status='ativo',
                plano_pre=0,
                plano_tipo='periodo',
                acesso_inicio=?,
                acesso_fim=?
            WHERE telegram_id=?
        """, (agora.isoformat(), acesso_fim.isoformat(), user_id))

    conn.commit()
    conn.close()

    return {"status": "ok"}
