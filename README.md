# رادار خبر و بازار - راه‌اندازی (حدود ۱۰ دقیقه)
1. در GitHub یک repo جدید بسازید و همه‌ی این فایل‌ها را آپلود کنید.
2. Settings > Pages > Source: Deploy from a branch > main > /docs
3. Actions > hourly-radar > Run workflow (اولین اجرا). بعد از آن هر ساعت خودکار اجرا می‌شود.
4. (اختیاری) Settings > Secrets and variables > Actions:
   - ANTHROPIC_API_KEY  دسته‌بندی هوشمند خبرها با Claude (بدون آن، کلیدواژه‌ای انجام می‌شود)
   - TELEGRAM_TOKEN و TELEGRAM_CHAT_ID  ارسال هشدار تلگرام برای خبرهای جدید
آدرس سایت: https://USERNAME.github.io/REPO/
فایل events.json فهرست رویدادهای مبنا است؛ تاریخ‌ها را بررسی و هر چه خواستید اضافه کنید.
منابع در بالای radar.py (FEEDS) هستند؛ آدرس فید CryptoWave و CoinMarketCap تأیید نشده است.
