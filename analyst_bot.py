import os
import asyncio
import aiohttp
import json
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from aiohttp import web
import logging

# ================ НАСТРОЙКИ ================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
CMC_API_KEY = os.environ.get('CMC_API_KEY')
PORT = int(os.environ.get('PORT', 10000))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================ API URLs ================
CMC_CRYPTO_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
CMC_GLOBAL_URL = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
CMC_FEAR_GREED_URL = "https://api.alternative.me/fng/"
CMC_GOLD_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
STOCKS_API_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"

MUST_INCLUDE = ['BTC', 'ETH', 'SOL']
TOP_STOCKS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA']

# ================ ФУНКЦИИ ================

async def get_crypto_data():
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    params = {'limit': 30, 'convert': 'USD'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(CMC_CRYPTO_URL, headers=headers, params=params) as response:
            data = await response.json()
            return data['data']

async def get_global_metrics():
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(CMC_GLOBAL_URL, headers=headers) as response:
            data = await response.json()
            return data['data']

async def get_fear_greed_index():
    async with aiohttp.ClientSession() as session:
        async with session.get(CMC_FEAR_GREED_URL) as response:
            data = await response.json()
            return data['data'][0]

async def get_gold_price():
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    params = {'symbol': 'PAXG', 'convert': 'USD'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(CMC_GOLD_URL, headers=headers, params=params) as response:
            data = await response.json()
            return data['data']['PAXG']

async def get_stock_price(symbol):
    """Получаем данные по одной акции через Yahoo Finance API"""
    url = f"{STOCKS_API_URL}{symbol}"
    params = {
        'range': '1d',
        'interval': '1d'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data['chart']['result'][0]
                    meta = result['meta']
                    
                    current_price = meta.get('regularMarketPrice', meta.get('previousClose', 0))
                    previous_close = meta.get('previousClose', current_price)
                    
                    if previous_close and current_price:
                        change_percent = ((current_price - previous_close) / previous_close) * 100
                    else:
                        change_percent = 0
                    
                    return {
                        'symbol': symbol,
                        'price': current_price,
                        'change_percent': change_percent,
                        'market_cap': meta.get('marketCap', 0)
                    }
                else:
                    logger.warning(f"Ошибка получения данных для {symbol}: {response.status}")
                    return None
    except Exception as e:
        logger.warning(f"Ошибка при получении данных акции {symbol}: {e}")
        return None

async def get_stocks_data():
    """Получаем данные по всем акциям параллельно"""
    tasks = [get_stock_price(symbol) for symbol in TOP_STOCKS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    stocks_data = []
    for result in results:
        if isinstance(result, dict) and result is not None:
            stocks_data.append(result)
        elif isinstance(result, Exception):
            logger.warning(f"Исключение при получении данных акции: {result}")
    
    return stocks_data

def format_number(num):
    if num is None:
        return "N/A"
    if num >= 1_000_000_000_000:
        return f"${num/1_000_000_000_000:.2f}T"
    elif num >= 1_000_000_000:
        return f"${num/1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"${num/1_000_000:.2f}M"
    else:
        return f"${num:,.2f}"

def get_emoji(change):
    if change is None:
        return "❓"
    if change > 5:
        return "🚀"
    elif change > 0:
        return "📈"
    elif change > -5:
        return "📉"
    else:
        return "💀"

def get_fear_greed_emoji(value):
    if value < 25:
        return "😱"
    elif value < 45:
        return "😰"
    elif value < 55:
        return "😐"
    elif value < 75:
        return "😊"
    else:
        return "🤑"

async def create_crypto_message():
    try:
        cryptos = await get_crypto_data()
        global_data = await get_global_metrics()
        fear_greed = await get_fear_greed_index()
        
        top_cryptos = []
        must_have = []
        
        for crypto in cryptos:
            symbol = crypto['symbol']
            if symbol in MUST_INCLUDE:
                must_have.append(crypto)
            else:
                top_cryptos.append(crypto)
        
        remaining_slots = 10 - len(must_have)
        final_list = must_have + top_cryptos[:remaining_slots]
        final_list.sort(key=lambda x: x['cmc_rank'])
        
        message = "🔥 <b>КРИПТО РЫНОК</b> 🔥\n\n"
        message += f"📊 <b>Общая капитализация:</b> {format_number(global_data['quote']['USD']['total_market_cap'])}\n"
        message += f"📈 <b>Изменение 24ч:</b> {global_data['quote']['USD']['total_market_cap_yesterday_percentage_change']:.2f}%\n"
        
        fg_value = int(fear_greed['value'])
        fg_emoji = get_fear_greed_emoji(fg_value)
        message += f"{fg_emoji} <b>Индекс страха/жадности:</b> {fg_value} ({fear_greed['value_classification']})\n\n"
        
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        message += "<b>ТОП-10 КРИПТОВАЛЮТ:</b>\n\n"
        
        for crypto in final_list:
            name = crypto['name']
            symbol = crypto['symbol']
            price = crypto['quote']['USD']['price']
            change_24h = crypto['quote']['USD']['percent_change_24h']
            market_cap = crypto['quote']['USD']['market_cap']
            emoji = get_emoji(change_24h)
            
            if price < 1:
                price_str = f"${price:.6f}"
            else:
                price_str = f"${price:,.2f}"
            
            message += f"{emoji} <b>{symbol}</b> ({name})\n"
            message += f"💰 {price_str} | "
            message += f"{'🟢' if change_24h > 0 else '🔴'} {change_24h:+.2f}%\n"
            message += f"📊 Cap: {format_number(market_cap)}\n\n"
        
        message += f"⏰ Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n"
        message += "\n💎 <b>MarvelMarket</b> - Твой гид в мире крипты!"
        
        return message
    
    except Exception as e:
        logger.error(f"Ошибка в create_crypto_message: {e}")
        return f"❌ Ошибка при получении данных: {str(e)}"

async def create_stocks_message():
    try:
        gold = await get_gold_price()
        gold_price = gold['quote']['USD']['price']
        gold_change = gold['quote']['USD']['percent_change_24h']
        
        stocks = await get_stocks_data()
        
        message = "🏆 <b>ЗОЛОТО И ТОП АКЦИИ</b> 🏆\n\n"
        
        message += "━━━━━━━━━━━━━━━━━━\n"
        message += f"🥇 <b>ЗОЛОТО (PAXG)</b>\n"
        message += f"💰 ${gold_price:,.2f}\n"
        message += f"{'🟢' if gold_change > 0 else '🔴'} {gold_change:+.2f}% (24h)\n\n"
        
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        message += "<b>ТОП АКЦИИ США:</b>\n\n"
        
        for stock in stocks:
            if not stock:
                continue
                
            symbol = stock['symbol']
            price = stock['price']
            change = stock['change_percent']
            market_cap = stock.get('market_cap', 0)
            emoji = get_emoji(change)
            
            message += f"{emoji} <b>{symbol}</b>\n"
            message += f"💰 ${price:,.2f} | "
            message += f"{'🟢' if change > 0 else '🔴'} {change:+.2f}%\n"
            if market_cap > 0:
                message += f"📊 Cap: {format_number(market_cap)}\n"
            message += "\n"
        
        message += f"⏰ Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n"
        message += "\n💼 <b>MarvelMarket</b> - Следим за рынками вместе!"
        
        return message
    
    except Exception as e:
        logger.error(f"Ошибка в create_stocks_message: {e}")
        return f"❌ Ошибка при получении данных акций: {str(e)}"

async def send_updates():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    while True:
        try:
            logger.info("Начало отправки обновлений...")
            
            crypto_msg = await create_crypto_message()
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=crypto_msg,
                parse_mode=ParseMode.HTML
            )
            
            await asyncio.sleep(5)
            
            stocks_msg = await create_stocks_message()
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=stocks_msg,
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"✅ Обновление отправлено: {datetime.now()}")
            
            # Ждем 1 час до следующего обновления
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в send_updates: {e}")
            await asyncio.sleep(300)  # Ждем 5 минут при ошибке

async def health_check(request):
    return web.Response(text="🚀 MarvelMarket Stats Bot is running!")

async def start_background_tasks(app):
    # Запускаем задачу в фоне
    app['bot_task'] = asyncio.create_task(send_updates())

async def cleanup_background_tasks(app):
    # Останавливаем задачу при завершении
    if 'bot_task' in app:
        app['bot_task'].cancel()
        try:
            await app['bot_task']
        except asyncio.CancelledError:
            pass

async def create_app():
    app = web.Application()
    
    # Добавляем маршруты
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    # Запускаем фоновые задачи
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    return app

async def main():
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌐 HTTP сервер запущен на порту {PORT}")
    logger.info("🚀 MarvelMarket Stats Bot запущен!")
    
    # Бесконечный цикл для поддержания работы
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # Проверяем наличие обязательных переменных
    if not all([TELEGRAM_BOT_TOKEN, CHANNEL_ID, CMC_API_KEY]):
        logger.error("❌ Не установлены все необходимые переменные окружения!")
        exit(1)
    
    logger.info("✅ Все переменные окружения установлены")
    asyncio.run(main())
