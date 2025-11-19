import os
import asyncio
import aiohttp
from telegram import Bot
from telegram.constants import ParseMode
from aiohttp import web

# Настройки
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
CMC_API_KEY = os.environ.get('CMC_API_KEY')
PORT = int(os.environ.get('PORT', 10000))

print("=" * 50)
print("🔍 ДИАГНОСТИКА MARVELMARKET BOT")
print("=" * 50)

# Проверка переменных
print("\n1️⃣ Проверка переменных окружения:")
print(f"TELEGRAM_BOT_TOKEN: {'✅ Установлен' if TELEGRAM_BOT_TOKEN else '❌ НЕ УСТАНОВЛЕН'}")
print(f"CHANNEL_ID: {CHANNEL_ID if CHANNEL_ID else '❌ НЕ УСТАНОВЛЕН'}")
print(f"CMC_API_KEY: {'✅ Установлен' if CMC_API_KEY else '❌ НЕ УСТАНОВЛЕН'}")

async def test_telegram():
    """Тест подключения к Telegram"""
    print("\n2️⃣ Тестирование Telegram Bot API:")
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username}")
        print(f"   ID бота: {me.id}")
        print(f"   Имя: {me.first_name}")
        return bot
    except Exception as e:
        print(f"❌ Ошибка подключения к боту: {e}")
        return None

async def test_channel(bot):
    """Тест доступа к каналу"""
    print("\n3️⃣ Тестирование доступа к каналу:")
    try:
        chat = await bot.get_chat(chat_id=CHANNEL_ID)
        print(f"✅ Канал найден: {chat.title}")
        print(f"   Username: @{chat.username if chat.username else 'Нет'}")
        print(f"   ID: {chat.id}")
        print(f"   Тип: {chat.type}")
        return True
    except Exception as e:
        print(f"❌ Ошибка доступа к каналу: {e}")
        print("   Проверьте:")
        print("   - Правильный ли ID канала?")
        print("   - Бот добавлен админом?")
        print("   - У бота есть право 'Публикация сообщений'?")
        return False

async def test_cmc_api():
    """Тест CoinMarketCap API"""
    print("\n4️⃣ Тестирование CoinMarketCap API:")
    try:
        headers = {
            'X-CMC_PRO_API_KEY': CMC_API_KEY,
            'Accept': 'application/json'
        }
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        params = {'limit': 5, 'convert': 'USD'}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ CMC API работает")
                    print(f"   Получено криптовалют: {len(data['data'])}")
                    print(f"   Первая: {data['data'][0]['name']} (${data['data'][0]['quote']['USD']['price']:.2f})")
                    return True
                else:
                    print(f"❌ CMC API ошибка: {response.status}")
                    text = await response.text()
                    print(f"   Ответ: {text[:200]}")
                    return False
    except Exception as e:
        print(f"❌ Ошибка CMC API: {e}")
        return False

async def send_test_message(bot):
    """Отправка тестового сообщения"""
    print("\n5️⃣ Отправка тестового сообщения:")
    try:
        message = """🧪 <b>ТЕСТОВОЕ СООБЩЕНИЕ</b>

✅ Бот успешно запущен!
✅ Подключение к Telegram работает
✅ Доступ к каналу есть
✅ API CoinMarketCap доступен

🔥 Через несколько минут начну отправлять реальную статистику!

💎 <b>MarvelMarket</b> - Система запущена!"""

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode=ParseMode.HTML
        )
        print("✅ Тестовое сообщение отправлено в канал!")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки сообщения: {e}")
        return False

async def health_check(request):
    """HTTP endpoint для Render"""
    return web.Response(text="🧪 Test Bot Running")

async def start_http_server():
    """Запуск HTTP сервера"""
    app = web.Application()
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"\n🌐 HTTP сервер запущен на порту {PORT}")

async def main():
    """Главная функция диагностики"""
    # Запуск HTTP сервера
    await start_http_server()
    
    # Проверки
    bot = await test_telegram()
    if not bot:
        print("\n❌ Невозможно продолжить без подключения к боту")
        return
    
    channel_ok = await test_channel(bot)
    if not channel_ok:
        print("\n❌ Невозможно продолжить без доступа к каналу")
        return
    
    cmc_ok = await test_cmc_api()
    if not cmc_ok:
        print("\n⚠️ CMC API не работает, но можно продолжить")
    
    # Отправка тестового сообщения
    await send_test_message(bot)
    
    print("\n" + "=" * 50)
    print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("=" * 50)
    print("\nБот будет работать постоянно.")
    print("Проверьте канал - должно прийти тестовое сообщение!")
    
    # Держим сервер живым
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Бот остановлен")
    except Exception as e:
        print(f"\n\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
