FROM mcr.microsoft.com/playwright/python:v1.40.0-focal

WORKDIR /app

# نسخ ملف المتطلبات أولاً لتحسين caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي الملفات
COPY . .

# تأكد من تثبيت المتصفحات (رغم أنها موجودة في الصورة)
RUN playwright install chromium

# أمر التشغيل
CMD ["python", "xbox_bot.py"]
