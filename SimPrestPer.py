import os
from telegram import (
    Update, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes, CallbackQueryHandler
)
from dotenv import load_dotenv

# Cargar variables locales
if os.path.exists(".env"):
    load_dotenv()

# Estados de la conversación
PEDIR_MONTO, PEDIR_MESES, PREGUNTAR_OTRO = range(3)
user_data_temp = {}

# --- Guardar mensajes ---
async def send_and_store(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs):
    """Envía mensaje y guarda ID para ocultarlo luego."""
    msg = await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    context.chat_data.setdefault("mensajes_bot", []).append(msg.message_id)
    return msg

def store_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda ID de mensaje del usuario."""
    context.chat_data.setdefault("mensajes_usuario", []).append(update.message.message_id)

# --- Ocultar mensajes (modo silencioso) ---
async def ocultar_mensajes(context: ContextTypes.DEFAULT_TYPE, chat_id: int, lista_ids: list):
    """Edita mensajes para ocultarlos, evitando spam de 'mensaje eliminado'."""
    for msg_id in lista_ids:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text="🕓 Mensaje ocultado por el bot"
            )
        except:
            pass

# --- Cálculo del préstamo ---
def calcular_prestamo_texto(deuda: float, meses: int) -> str:
    if deuda <= 1500:
        interes_anual, desgravamen = 30, 0.805
    elif deuda <= 3000:
        interes_anual, desgravamen = 28, 0.705
    elif deuda <= 10000:
        interes_anual, desgravamen = 25, 0.605
    elif deuda <= 25000:
        interes_anual, desgravamen = 23, 0.505
    elif deuda <= 80000:
        interes_anual, desgravamen = 21, 0.405
    elif deuda <= 150000:
        interes_anual, desgravamen = 18, 0.305
    else:
        interes_anual, desgravamen = 15, 0.205

    tasa_mensual = interes_anual / 100 / 12
    cuota_mensual = round(
        (deuda * tasa_mensual * (1 + tasa_mensual) ** meses) /
        ((1 + tasa_mensual) ** meses - 1), 2
    )

    saldo_pendiente = deuda
    sumatoria_intereses = 0
    filas = []

    for i in range(1, meses + 1):
        interes = round(saldo_pendiente * tasa_mensual, 2)
        capital = round(cuota_mensual - interes, 2)
        saldo_pendiente = round(saldo_pendiente - capital, 2)
        sumatoria_intereses += interes
        filas.append([
            str(i),
            f"S/{cuota_mensual:,.2f}",
            f"S/{interes:,.2f}",
            f"S/{capital:,.2f}",
            f"S/{saldo_pendiente:,.2f}"
        ])

    col_nombres = ["Mes", "Cuota", "Interés", "Capital", "Saldo"]
    anchos = [max(len(col), max(len(f[i]) for f in filas)) for i, col in enumerate(col_nombres)]

    tabla = " ".join(col.ljust(anchos[i]) for i, col in enumerate(col_nombres)) + "\n"
    for fila in filas:
        tabla += " ".join(valor.ljust(anchos[i]) for i, valor in enumerate(fila)) + "\n"

    total_pagado = deuda + sumatoria_intereses
    resumen = (
        f"\n💰 Monto de préstamo: S/{deuda:,.2f}\n"
        f"⏳ Tiempo en meses: {meses}\n"
        f"📈 Tasa de interés anual: {interes_anual}%\n"
        f"🛡️ Desgravamen: {desgravamen}%\n"
        f"💵 Total pagado: S/{total_pagado:,.2f}\n"
        f"📊 Total intereses: S/{sumatoria_intereses:,.2f}"
    )
    return f"📊 *Tabla de amortización:*\n```\n{tabla}\n```\n{resumen}"

# --- Conversación ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["mensajes_bot"] = []
    context.chat_data["mensajes_usuario"] = []
    await send_and_store(context, update.effective_chat.id,
        "Hola 👋 Soy el simulador de préstamos.\nIngresa el monto del préstamo (en soles):"
    )
    return PEDIR_MONTO

async def recibir_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store_user_message(update, context)
    texto = update.message.text.strip()
    if not texto.replace(".", "", 1).isdigit():
        await send_and_store(context, update.effective_chat.id, "❌ Ingresa un número válido para el monto.")
        return PEDIR_MONTO

    deuda = float(texto)
    if deuda <= 0:
        await send_and_store(context, update.effective_chat.id, "❌ El monto debe ser mayor a cero.")
        return PEDIR_MONTO

    user_data_temp[update.effective_user.id] = {"deuda": deuda}
    await send_and_store(context, update.effective_chat.id, "Ahora ingresa el tiempo en meses:")
    return PEDIR_MESES

async def recibir_meses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store_user_message(update, context)
    texto = update.message.text.strip()
    if not texto.isdigit():
        await send_and_store(context, update.effective_chat.id, "❌ Ingresa un número válido de meses.")
        return PEDIR_MESES

    meses = int(texto)
    if meses <= 0:
        await send_and_store(context, update.effective_chat.id, "❌ El número de meses debe ser mayor a cero.")
        return PEDIR_MESES

    deuda = user_data_temp[update.effective_user.id]["deuda"]
    resultado = calcular_prestamo_texto(deuda, meses)
    await send_and_store(context, update.effective_chat.id, resultado, parse_mode="Markdown")

    botones = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Otra simulación", callback_data="restart_bot")],
        [InlineKeyboardButton("❌ Salir", callback_data="exit_bot")]
    ])
    await send_and_store(context, update.effective_chat.id, "¿Qué deseas hacer ahora?", reply_markup=botones)
    return PREGUNTAR_OTRO

# --- Botones ---
async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "restart_bot":
        context.chat_data["mensajes_bot"] = []
        context.chat_data["mensajes_usuario"] = []
        await query.message.reply_text("Ingresa el monto del préstamo:", reply_markup=ReplyKeyboardRemove())
        return PEDIR_MONTO

    elif query.data == "exit_bot":
        chat_id = query.message.chat_id
        # Ocultar mensajes del bot y del usuario
        await ocultar_mensajes(context, chat_id, context.chat_data.get("mensajes_bot", []))
        await ocultar_mensajes(context, chat_id, context.chat_data.get("mensajes_usuario", []))
        # Mensaje final
        await query.message.reply_text("Gracias por usar el simulador. 👋", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store_user_message(update, context)
    await update.message.reply_text("❌ Simulación cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Main ---
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    URL = os.getenv("RAILWAY_STATIC_URL")
    PORT = int(os.getenv("PORT", 8080))

    if not TOKEN:
        raise RuntimeError("❌ Falta BOT_TOKEN en las variables de entorno.")

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PEDIR_MONTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_monto)],
            PEDIR_MESES: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_meses)],
            PREGUNTAR_OTRO: [CallbackQueryHandler(manejar_botones)],
        },
        fallbacks=[CommandHandler("cancel", cancelar)],
    )
    app.add_handler(conv_handler)

    if URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"https://{URL}/{TOKEN}"
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()