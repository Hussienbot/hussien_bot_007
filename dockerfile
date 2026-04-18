FROM python:3.12-slim

WORKDIR /app

# تثبيت تبعيات النظام اللازمة لتشغيل Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت متصفح Chromium الخاص بـ Playwright
RUN playwright install chromium
RUN playwright install-deps

# نسخ باقي ملفات المشروع
COPY . .

# أمر تشغيل البوت
CMD ["python", "xbox_bot.py"]