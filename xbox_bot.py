#!/usr/bin/env python3
"""
Telegram Bot for Xbox Account Checker
"""

import asyncio
import csv
from io import BytesIO, StringIO
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# استيراد الدوال من xbox_checker
from xbox_checker import process_account, parse_accounts_from_text

# تم وضع التوكن الخاص بك هنا
TOKEN = "8634744371:AAEQDR7IzqW0HlO2o1BtwJyfHMz6iFhYugA"

# ------------------- أوامر البوت -------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 **بوت فحص حسابات Xbox**\n\n"
        "• أرسل `/check` لبدء العملية.\n"
        "• ستحتاج إلى رفع ملف `txt` يحتوي على الحسابات (كل سطر بالصيغة `email:password`).\n"
        "• البوت سيقوم بفحص جميع الحسابات تلقائياً (واحداً تلو الآخر) ويرسل النتائج.\n"
        "• في النهاية ستحصل على ملف CSV وملخص.\n\n"
        "⚠️ البوت يعمل في وضع **headless** (المتصفحات تعمل خلفية).",
        parse_mode='Markdown'
    )

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يطلب من المستخدم رفع ملف txt"""
    context.user_data['awaiting_file'] = True
    await update.message.reply_text(
        "📤 الرجاء رفع ملف نصي `txt` يحتوي على الحسابات.\n"
        "كل سطر: `email:password`\n"
        "(يمكنك إرسال الملف مباشرة الآن)."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الملف المرفوع"""
    if not context.user_data.get('awaiting_file'):
        await update.message.reply_text("❌ لم أطلب ملفاً. أرسل /check أولاً.")
        return
    
    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ يرجى رفع ملف نصي بصيغة .txt")
        return
    
    # تحميل الملف
    file = await document.get_file()
    content = await file.download_as_bytearray()
    text = content.decode('utf-8', errors='ignore')
    
    # استخراج الحسابات
    accounts = parse_accounts_from_text(text)
    if not accounts:
        await update.message.reply_text("❌ لم يتم العثور على حسابات صالحة في الملف (يجب أن كل سطر يحتوي على email:password).")
        return
    
    # تخزين الحسابات في user_data
    context.user_data['accounts'] = accounts
    context.user_data['results'] = []
    context.user_data['current_index'] = 0
    context.user_data['awaiting_file'] = False
    
    await update.message.reply_text(f"✅ تم استلام {len(accounts)} حساب. سأبدأ الفحص الآن...")
    
    # بدء الفحص التلقائي
    await process_next_account(update, context)

async def process_next_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص الحساب التالي (تلقائي)"""
    accounts = context.user_data.get('accounts', [])
    index = context.user_data.get('current_index', 0)
    
    if index >= len(accounts):
        # انتهى الفحص
        await finalize_results(update, context)
        return
    
    account = accounts[index]
    await update.message.reply_text(f"🔄 جاري فحص {index+1}/{len(accounts)}: `{account['email']}`", parse_mode='Markdown')
    
    # فحص الحساب (headless=True)
    result = await process_account(account, headless=True)
    
    # تخزين النتيجة
    context.user_data.setdefault('results', []).append(result)
    context.user_data['current_index'] = index + 1
    
    # إرسال نتيجة هذا الحساب
    if result['success'] and result['has_console']:
        status = "✅ **مع جهاز**"
    elif result['success']:
        status = "⚠️ **مسجل ولا جهاز**"
    else:
        status = "❌ **فشل**"
    
    await update.message.reply_text(
        f"{status}\n"
        f"📧 {result['email']}\n"
        f"📝 {result['console_info']}"
    )
    
    # انتظار قصير قبل الانتقال إلى التالي (لتجنب الإغراق)
    await asyncio.sleep(2)
    
    # متابعة الحساب التالي
    await process_next_account(update, context)

async def finalize_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال النتائج النهائية (ملف CSV وملخص)"""
    results = context.user_data.get('results', [])
    if not results:
        await update.message.reply_text("لا توجد نتائج لإرسالها.")
        return
    
    # إنشاء ملف CSV في الذاكرة
    output = StringIO()
    fieldnames = ['email', 'password', 'success', 'has_console', 'console_info', 'timestamp']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)
    output.seek(0)
    
    # إرسال الملف
    await update.message.reply_document(
        document=BytesIO(output.getvalue().encode('utf-8')),
        filename=f'xbox_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )
    
    # إحصائيات
    total = len(results)
    with_device = sum(1 for r in results if r['success'] and r['has_console'])
    logged_no_device = sum(1 for r in results if r['success'] and not r['has_console'])
    failed = sum(1 for r in results if not r['success'])
    
    summary = (
        f"📊 **النتائج النهائية**\n"
        f"───────────\n"
        f"✅ مع جهاز: {with_device}\n"
        f"⚠️ مسجل ولا جهاز: {logged_no_device}\n"
        f"❌ فشل: {failed}\n"
        f"───────────\n"
        f"📌 الإجمالي: {total}"
    )
    await update.message.reply_text(summary, parse_mode='Markdown')
    
    # تنظيف البيانات
    context.user_data.clear()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية ومسح البيانات"""
    context.user_data.clear()
    await update.message.reply_text("❌ تم إلغاء العملية ومسح جميع البيانات المؤقتة.")

# ------------------- تشغيل البوت -------------------

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("🤖 البوت يعمل... اضغط Ctrl+C للإيقاف.")
    app.run_polling()

if __name__ == "__main__":
    main()