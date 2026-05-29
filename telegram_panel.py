import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== CONFIG =====
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

GITHUB_TOKEN = "YOUR_GITHUB_TOKEN"
OWNER = "YOUR_USERNAME"
REPO = "YOUR_REPO"
WORKFLOW = "scanner.yml"

URL = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW}/dispatches"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# ===== TRIGGER =====
def run_github():
    r = requests.post(URL, json={"ref": "main"}, headers=headers)
    return r.status_code

# ===== MENU =====
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Run Scanner", callback_data="run")]
    ])

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Trading Panel Ready", reply_markup=menu())

# ===== BUTTON =====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "run":
        status = run_github()
        await query.edit_message_text(
            f"🚀 Trigger sent to GitHub\nStatus: {status}",
            reply_markup=menu()
        )

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()

if __name__ == "__main__":
    main()
