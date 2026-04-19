import os
import asyncio
import csv
from io import BytesIO, StringIO
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from xbox_checker import process_account, parse_accounts_from_text

TOKEN = os.environ.get("TOKEN")  # يقرأ من متغير البيئة

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 بوت فحص حسابات Xbox جاهز. أرسل /check لبدء الفحص.")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['awaiting_file'] = True
    await update.message.reply_text("📤 أرسل ملف txt يحتوي على الحسابات (كل سطر email:password)")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_file'):
        await update.message.reply_text("❌ أرسل /check أولاً.")
        return
    doc = update.message.document
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ يرجى رفع ملف txt")
        return
    file = await doc.get_file()
    content = await file.download_as_bytearray()
    text = content.decode('utf-8', errors='ignore')
    accounts = parse_accounts_from_text(text)
    if not accounts:
        await update.message.reply_text("❌ لا توجد حسابات صالحة")
        return
    context.user_data['accounts'] = accounts
    context.user_data['results'] = []
    context.user_data['current_index'] = 0
    context.user_data['awaiting_file'] = False
    await update.message.reply_text(f"✅ تم استلام {len(accounts)} حساب. بدء الفحص...")
    await process_next_account(update, context)

async def process_next_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = context.user_data.get('accounts', [])
    idx = context.user_data.get('current_index', 0)
    if idx >= len(accounts):
        await finalize_results(update, context)
        return
    account = accounts[idx]
    await update.message.reply_text(f"🔄 جاري فحص {idx+1}/{len(accounts)}: {account['email']}")
    result = await process_account(account, headless=True)
    context.user_data.setdefault('results', []).append(result)
    context.user_data['current_index'] = idx + 1
    if result['success'] and result['has_console']:
        status = "✅ مع جهاز"
    elif result['success']:
        status = "⚠️ مسجل ولا جهاز"
    else:
        status = "❌ فشل"
    await update.message.reply_text(f"{status}\n📧 {result['email']}\n📝 {result['console_info']}")
    await asyncio.sleep(2)
    await process_next_account(update, context)

async def finalize_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data.get('results', [])
    if not results:
        await update.message.reply_text("لا توجد نتائج.")
        return
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=['email','password','success','has_console','console_info','timestamp'])
    writer.writeheader()
    writer.writerows(results)
    output.seek(0)
    await update.message.reply_document(document=BytesIO(output.getvalue().encode()), filename='results.csv')
    with_device = sum(1 for r in results if r['success'] and r['has_console'])
    no_device = sum(1 for r in results if r['success'] and not r['has_console'])
    failed = sum(1 for r in results if not r['success'])
    await update.message.reply_text(f"📊 النتائج:\n✅ مع جهاز: {with_device}\n⚠️ بدون جهاز: {no_device}\n❌ فشل: {failed}")
    context.user_data.clear()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("تم الإلغاء.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
