import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes
)
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
if os.path.exists(".env"):
    load_dotenv()

# Estados de la conversación
PEDIR_MONTO, PEDIR_MESES = range(2)
user_data_temp = {}

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
    cuota_mensual = round((deuda * tasa_mensual * (1 + tasa_mensual) ** meses) /
                          ((1 + tasa_mensual) ** meses - 1), 2)

    saldo_pendiente = deuda
    sumatoria_intereses = 0
    tabla = "Mes\tCuota\t\tInterés\t\tCapital\t\tSaldo\n" + "-" * 60 + "\n"

    for i in range(1, meses + 1):
        interes = round(saldo_pendiente * tasa_mensual, 2)
        capital = round(cuota_mensual - interes, 2)
        saldo_pendiente = round(saldo_pendiente - capital, 2)
        sumatoria_intereses += interes
        tabla += f"{i}\tS/{cuota_mensual:,.2f}\tS/{interes:,.2f}\tS/{capital:,.2f}\tS/{saldo_pendiente:,.2f}\n"

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
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Ingresa un número válido de meses.")
        return PEDIR_MESES

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Simulación cancelada.")
    return ConversationHandler.END

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    URL = os.getenv("RAILWAY_STATIC_URL")
    PORT = int(os.getenv("PORT", 8080))

    print("=== VARIABLES DE ENTORNO ===")
    print(f"BOT_TOKEN: {'OK' if TOKEN else 'NO ENCONTRADO'}")
    print(f"RAILWAY_STATIC_URL: {URL if URL else 'VACÍO'}")
    print(f"PORT: {PORT}")
    print("============================")

    if not TOKEN:
        raise RuntimeError("❌ Error: Falta BOT_TOKEN en las variables de entorno.")

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PEDIR_MONTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_monto)],
            PEDIR_MESES: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_meses)],
        },
        fallbacks=[CommandHandler("cancel", cancelar)],
    )
    app.add_handler(conv_handler)

    if URL:
        print("🚀 Iniciando en modo Webhook...")
        try:
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=TOKEN,
                webhook_url=f"https://{URL}/{TOKEN}"
            )
        except Exception as e:
            print(f"⚠ Error al iniciar webhook: {e}")
            print("🔄 Cambiando a modo Polling...")
            app.run_polling()
    else:
        print("⚠ No se detectó URL, usando modo Polling...")
        app.run_polling()

if __name__ == "__main__":
    main()