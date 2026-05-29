import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

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

# ===== UI =====
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Run Scanner", callback_data="run")]
    ])

# ===== START =====
def start(update: Update, context):
    update.message.reply_text("📊 Trading Panel Active", reply_markup=menu())

# ===== BUTTON =====
def button(update: Update, context):
    q = update.callback_query
    q.answer()

    if q.data == "run":
        code = run_github()
        q.edit_message_text(f"🚀 Trigger sent\nStatus: {code}", reply_markup=menu())

# ===== MAIN =====
def main():
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
