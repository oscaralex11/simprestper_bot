import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes
)
from dotenv import load_dotenv

# Cargar variables de entorno en local
if os.path.exists(".env"):
    load_dotenv()

# Estados de conversación
PEDIR_MONTO, PEDIR_MESES, PREGUNTAR_OTRO = range(3)
user_data_temp = {}

def calcular_prestamo_texto(deuda: float, meses: int) -> str:
    """Genera la tabla de amortización con ancho dinámico."""
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
    cuota_mensual = round((deuda * tasa_mensual * (1 + tasa_mensual) ** meses) /
                          ((1 + tasa_mensual) ** meses - 1), 2)

    saldo_pendiente = deuda
    sumatoria_intereses = 0
    filas = []

    # Generar filas de la tabla
    for i in range(1, meses + 1):
        interes = round(saldo_pendiente * tasa_mensual, 2)
        capital = round(cuota_mensual - interes, 2)
        saldo_pendiente = round(saldo_pendiente - capital, 2)
        sumatoria_intereses += interes
        filas.append([str(i), f"S/{cuota_mensual:,.2f}", f"S/{interes:,.2f}",
                      f"S/{capital:,.2f}", f"S/{saldo_pendiente:,.2f}"])

    # Calcular ancho de columnas dinámicamente
    col_nombres = ["Mes", "Cuota", "Interés", "Capital", "Saldo"]
    anchos = [len(col) for col in col_nombres]
    for fila in filas:
        for idx, valor in enumerate(fila):
            if len(valor) > anchos[idx]:
                anchos[idx] = len(valor)

    # Construir tabla alineada
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
    await update.message.reply_text(
        "Hola 👋 Soy el simulador de préstamos.\n"
        "Por favor ingresa el monto del préstamo (en soles):"
    )
    return PEDIR_MONTO

async def recibir_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        deuda = float(update.message.text)
        if deuda <= 0:
            raise ValueError
        user_data_temp[update.effective_user.id] = {"deuda": deuda}
        await update.message.reply_text("Perfecto ✅\nAhora ingresa el tiempo en meses:")
        return PEDIR_MESES
    except ValueError:
        await update.message.reply_text("❌ Ingresa un número válido para el monto.")
        return PEDIR_MONTO

async def recibir_meses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        meses = int(update.message.text)
        if meses <= 0:
            raise ValueError
        deuda = user_data_temp[update.effective_user.id]["deuda"]
        resultado = calcular_prestamo_texto(deuda, meses)
        await update.message.reply_markdown(resultado)

        # Mostrar botones
        keyboard = [["Sí", "No"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("¿Quieres hacer otra simulación?", reply_markup=reply_markup)

        return PREGUNTAR_OTRO
    except ValueError:
        await update.message.reply_text("❌ Ingresa un número válido de meses.")
        return PEDIR_MESES

async def preguntar_otro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    respuesta = update.message.text.lower()
    if respuesta in ["sí", "si"]:
        await update.message.reply_text(
            "Perfecto, ingresa el monto del préstamo:",
            reply_markup=ReplyKeyboardRemove()
        )
        return PEDIR_MONTO
    else:
        await update.message.reply_text(
            "Gracias por usar el simulador. 👋",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Simulación cancelada.",
        reply_markup=ReplyKeyboardRemove()
    )
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
            PREGUNTAR_OTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, preguntar_otro)],
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