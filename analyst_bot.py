import os
import asyncio
import aiohttp
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
CMC_QUOTES_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"

# Списки активов
TOP_CRYPTO_SYMBOLS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'LINK', 'MATIC']
STABLE_COINS = ['USDT', 'USDC', 'BUSD', 'DAI', 'UST']
STOCKS_SYMBOLS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA']
METALS_SYMBOLS = ['PAXG']  # Золото

# ================ ФУНКЦИИ ================

async def make_cmc_request(url, params=None):
    """Универсальная функция для запросов к CMC API"""
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.error(f"Ошибка CMC API: {response.status}")
                return None

async def get_crypto_data(limit=100):
    """Получаем данные по криптовалютам"""
    params = {'limit': limit, 'convert': 'USD'}
    data = await make_cmc_request(CMC_CRYPTO_URL, params)
    return data['data'] if data else []

async def get_global_metrics():
    """Получаем глобальную статистику"""
    data = await make_cmc_request(CMC_GLOBAL_URL)
    return data['data'] if data else None

async def get_fear_greed_index():
    """Получаем индекс страха и жадности"""
    async with aiohttp.ClientSession() as session:
        async with session.get(CMC_FEAR_GREED_URL) as response:
            data = await response.json()
            return data['data'][0]

async def get_specific_assets(symbols):
    """Получаем данные по конкретным активам (акции, металлы)"""
    params = {'symbol': ','.join(symbols), 'convert': 'USD'}
    data = await make_cmc_request(CMC_QUOTES_URL, params)
    return data['data'] if data else {}

def format_number(num):
    """Форматирование больших чисел"""
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
    """Получаем эмодзи по изменению цены"""
    if change is None:
        return "❓"
    if change > 10:
        return "🚀"
    elif change > 5:
        return "🔥"
    elif change > 0:
        return "📈"
    elif change > -5:
        return "📉"
    elif change > -10:
        return "💀"
    else:
        return "🪦"

def get_fear_greed_emoji(value):
    """Эмодзи для индекса страха/жадности"""
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

def format_price(price):
    """Форматирование цены"""
    if price < 0.01:
        return f"${price:.8f}"
    elif price < 1:
        return f"${price:.6f}"
    else:
        return f"${price:,.2f}"

async def create_crypto_message():
    try:
        # Получаем все данные
        all_cryptos = await get_crypto_data(100)
        global_data = await get_global_metrics()
        fear_greed = await get_fear_greed_index()
        specific_assets = await get_specific_assets(STOCKS_SYMBOLS + METALS_SYMBOLS)
        
        if not all_cryptos:
            return "❌ Ошибка при получении данных крипторынка"
        
        # Фильтруем криптовалюты (убираем стейбкоины)
        filtered_cryptos = [c for c in all_cryptos if c['symbol'] not in STABLE_COINS]
        
        # Находим BTC и ETH
        btc = next((c for c in filtered_cryptos if c['symbol'] == 'BTC'), None)
        eth = next((c for c in filtered_cryptos if c['symbol'] == 'ETH'), None)
        
        # Топ роста (исключая BTC и ETH)
        top_gainers = sorted(
            [c for c in filtered_cryptos if c['symbol'] not in ['BTC', 'ETH']],
            key=lambda x: x['quote']['USD']['percent_change_24h'],
            reverse=True
        )[:5]
        
        # Топ падения (исключая BTC и ETH)
        top_losers = sorted(
            [c for c in filtered_cryptos if c['symbol'] not in ['BTC', 'ETH']],
            key=lambda x: x['quote']['USD']['percent_change_24h']
        )[:5]
        
        # Топ по капитализации (исключая BTC, ETH и те что уже в gainers/losers)
        excluded_symbols = ['BTC', 'ETH'] + [c['symbol'] for c in top_gainers] + [c['symbol'] for c in top_losers]
        top_by_market_cap = sorted(
            [c for c in filtered_cryptos if c['symbol'] not in excluded_symbols],
            key=lambda x: x['quote']['USD']['market_cap'],
            reverse=True
        )[:5]
        
        message = "🔥 <b>MARVEL MARKET DIGEST</b> 🔥\n\n"
        
        # Глобальная статистика
        if global_data:
            total_cap = global_data['quote']['USD']['total_market_cap']
            total_volume = global_data['quote']['USD']['total_volume_24h']
            btc_dominance = global_data['btc_dominance']
            eth_dominance = global_data['eth_dominance']
            
            message += "📊 <b>ОБЗОР РЫНКА</b>\n"
            message += f"• Капитализация: {format_number(total_cap)}\n"
            message += f"• Объем 24ч: {format_number(total_volume)}\n"
            message += f"• Доминирование BTC: {btc_dominance:.1f}%\n"
            message += f"• Доминирование ETH: {eth_dominance:.1f}%\n"
        
        # Индекс страха/жадности
        fg_value = int(fear_greed['value'])
        fg_emoji = get_fear_greed_emoji(fg_value)
        message += f"• {fg_emoji} Индекс страха/жадности: <b>{fg_value}</b> ({fear_greed['value_classification']})\n\n"
        
        # Биткоин и Эфир
        message += "👑 <b>ЛИДЕРЫ РЫНКА</b>\n"
        if btc:
            btc_data = btc['quote']['USD']
            message += f"₿ <b>BITCOIN</b>\n"
            message += f"  {format_price(btc_data['price'])} | "
            message += f"{'🟢' if btc_data['percent_change_24h'] > 0 else '🔴'} {btc_data['percent_change_24h']:+.2f}%\n"
        
        if eth:
            eth_data = eth['quote']['USD']
            message += f"🔷 <b>ETHEREUM</b>\n"
            message += f"  {format_price(eth_data['price'])} | "
            message += f"{'🟢' if eth_data['percent_change_24h'] > 0 else '🔴'} {eth_data['percent_change_24h']:+.2f}%\n"
        
        message += "\n"
        
        # Топ роста
        message += "🚀 <b>ТОП РОСТА (24ч)</b>\n"
        for crypto in top_gainers:
            quote = crypto['quote']['USD']
            emoji = get_emoji(quote['percent_change_24h'])
            message += f"{emoji} <b>{crypto['symbol']}</b>\n"
            message += f"  {format_price(quote['price'])} | 🟢 +{quote['percent_change_24h']:.2f}%\n"
        
        message += "\n"
        
        # Топ падения
        message += "💀 <b>ТОП ПАДЕНИЯ (24ч)</b>\n"
        for crypto in top_losers:
            quote = crypto['quote']['USD']
            emoji = get_emoji(quote['percent_change_24h'])
            message += f"{emoji} <b>{crypto['symbol']}</b>\n"
            message += f"  {format_price(quote['price'])} | 🔴 {quote['percent_change_24h']:+.2f}%\n"
        
        message += "\n"
        
        # Традиционные активы
        message += "💼 <b>ТРАДИЦИОННЫЕ АКТИВЫ</b>\n"
        
        # Золото
        if 'PAXG' in specific_assets:
            gold = specific_assets['PAXG']['quote']['USD']
            message += f"🥇 <b>ЗОЛОТО (PAXG)</b>\n"
            message += f"  ${gold['price']:,.2f} | "
            message += f"{'🟢' if gold['percent_change_24h'] > 0 else '🔴'} {gold['percent_change_24h']:+.2f}%\n"
        
        # Акции
        for stock_symbol in STOCKS_SYMBOLS:
            if stock_symbol in specific_assets:
                stock = specific_assets[stock_symbol]['quote']['USD']
                change_emoji = '🟢' if stock['percent_change_24h'] > 0 else '🔴'
                message += f"📊 <b>{stock_symbol}</b> | ${stock['price']:,.2f} | {change_emoji} {stock['percent_change_24h']:+.2f}%\n"
        
        message += f"\n⏰ Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n"
        message += "\n💎 <b>MarvelMarket</b> - Твой гид в мире инвестиций!"
        
        return message
    
    except Exception as e:
        logger.error(f"Ошибка в create_crypto_message: {e}")
        return f"❌ Ошибка при получении данных: {str(e)}"

async def send_updates():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    while True:
        try:
            logger.info("Начало отправки обновлений...")
            
            message = await create_crypto_message()
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
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
