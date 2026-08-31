# Zangora Film Bot

Kino kodlari orqali film topib beruvchi Telegram bot. Majburiy obuna (@zangorafilm) tekshiruvi bilan.

## Hozirgi funksiyalar

- `/start` — foydalanuvchini kutib oladi
- Majburiy kanalga a'zolikni tekshiradi (@zangorafilm), a'zo bo'lmasa "Kanalga qo'shilish" + "✅ Tekshirish" tugmalari chiqadi
- A'zo bo'lgach — logotip rasm bilan chiroyli salomlashuv, ostida **🎬 Kino kodlari** (kanalga olib boradi) va **⚙️ Admin panel** tugmalari
- Admin panel va kino kodlari bazasi — keyingi bosqichda to'ldiriladi (hozircha joy tayyor)

## Loyihani ishga tushirish (lokal)

1. Python 3.10+ o'rnatilgan bo'lishi kerak
2. Kutubxonalarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```
3. `.env` faylida `BOT_TOKEN` va kerak bo'lsa `ADMIN_IDS` ni to'ldiring (o'zingizning Telegram ID'ingizni [@userinfobot](https://t.me/userinfobot) orqali bilib olishingiz mumkin)
4. Botni ishga tushiring:
   ```bash
   python bot.py
   ```

## MUHIM: bot admin bo'lishi kerak

Majburiy obunani tekshirish ishlashi uchun bot **@zangorafilm** kanaliga **admin** qilib qo'shilgan bo'lishi shart (aks holda `get_chat_member` xato qaytaradi).

## Railway'ga joylash

1. Loyihani GitHub'ga yuklang (`.env` fayli **hech qachon** yuklanmasin — u `.gitignore`da bor)
2. Railway'da yangi project yarating va shu GitHub repo'ni ulang
3. Railway "Variables" bo'limida quyidagilarni qo'shing:
   - `BOT_TOKEN` — bot tokeningiz
   - `CHANNEL_USERNAME` — `@zangorafilm`
   - `ADMIN_IDS` — sizning Telegram ID'ingiz
4. Railway avtomatik `Procfile`dagi `worker: python bot.py` buyrug'ini ishga tushiradi

## Xavfsizlik bo'yicha eslatma

Bot tokeningiz suhbatda ochiq yuborilgan edi. Tavsiya: [@BotFather](https://t.me/BotFather) orqali `/revoke` qilib yangi token oling va shu yangisini `.env` (lokal) va Railway "Variables" bo'limiga qo'ying. Tokenni hech qachon GitHub'ga (kodga yozib) yuklamang.

## Loyiha tuzilishi

```
zangorafilm_bot/
├── bot.py                  # botni ishga tushiruvchi asosiy fayl
├── config.py                # .env dan sozlamalarni o'qiydi
├── handlers/
│   ├── user_handlers.py     # /start, obuna tekshiruvi, asosiy menyu
│   └── admin_handlers.py    # admin panel (keyingi bosqichda to'ldiriladi)
├── assets/
│   └── welcome.jpg           # salomlashuv rasmi (Zangora Film logotipi)
├── requirements.txt
├── Procfile                  # Railway uchun
├── .env                      # tokenlar (GitHub'ga yuklanmaydi)
└── .env.example
```

## Keyingi bosqich

- Admin panel: kino qo'shish/o'chirish, statistikalar (reply keyboard, faqat adminlarga ko'rinadi)
- Kino kodlari bazasi: kod yuborilganda tegishli filmni topib berish (SQLite yoki boshqa DB bilan)
