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
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY', 'cn5l71pr01qusj7k9e10cn5l71pr01qusj7k9e1g')  # бесплатный ключ
PORT = int(os.environ.get('PORT', 10000))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================ API URLs ================
CMC_CRYPTO_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
CMC_GLOBAL_URL = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
CMC_FEAR_GREED_URL = "https://api.alternative.me/fng/"
CMC_GOLD_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
FINNHUB_URL = "https://finnhub.io/api/v1/quote"

# Списки активов
STABLE_COINS = ['USDT', 'USDC', 'BUSD', 'DAI', 'UST']
STOCKS_SYMBOLS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA']

# ================ ФУНКЦИИ ================

async def make_cmc_request(url, params=None):
    """Универсальная функция для запросов к CMC API"""
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Ошибка CMC API {url}: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Ошибка запроса к CMC {url}: {e}")
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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(CMC_FEAR_GREED_URL) as response:
                data = await response.json()
                return data['data'][0]
    except Exception as e:
        logger.error(f"Ошибка получения индекса страха/жадности: {e}")
        return {'value': 50, 'value_classification': 'Neutral'}

async def get_gold_price():
    """Получаем цену золота из CMC"""
    params = {'symbol': 'PAXG', 'convert': 'USD'}
    data = await make_cmc_request(CMC_GOLD_URL, params)
    if data and 'data' in data and 'PAXG' in data['data']:
        return data['data']['PAXG']
    return None

async def get_stock_data(symbol):
    """Получаем данные по акциям через Finnhub API"""
    params = {
        'symbol': symbol,
        'token': FINNHUB_API_KEY
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FINNHUB_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    current_price = data.get('c', 0)  # текущая цена
                    previous_close = data.get('pc', current_price)  # цена закрытия предыдущего дня
                    change = data.get('d', 0)  # изменение цены
                    change_percent = data.get('dp', 0)  # изменение в процентах
                    
                    # Если процент изменения не получен, вычисляем вручную
                    if change_percent == 0 and previous_close and previous_close > 0 and current_price > 0:
                        change_percent = ((current_price - previous_close) / previous_close) * 100
                    
                    logger.info(f"Акция {symbol}: цена={current_price}, изменение={change_percent:.2f}%")
                    
                    return {
                        'symbol': symbol,
                        'price': current_price,
                        'change_percent': change_percent,
                        'change_amount': change
                    }
                else:
                    logger.warning(f"Ошибка Finnhub для {symbol}: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Ошибка Finnhub для {symbol}: {e}")
        return None

async def get_all_stocks_data():
    """Получаем данные по всем акциям"""
    tasks = [get_stock_data(symbol) for symbol in STOCKS_SYMBOLS]
    results = await asyncio.gather(*tasks)
    
    stocks_data = {}
    for result in results:
        if result and result['price'] > 0:  # Проверяем что данные валидные
            stocks_data[result['symbol']] = result
    
    return stocks_data

def safe_format_number(num):
    """Безопасное форматирование больших чисел"""
    if num is None:
        return "N/A"
    try:
        num = float(num)
        if num >= 1_000_000_000_000:
            return f"${num/1_000_000_000_000:.2f}T"
        elif num >= 1_000_000_000:
            return f"${num/1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"${num/1_000_000:.2f}M"
        else:
            return f"${num:,.2f}"
    except (TypeError, ValueError):
        return "N/A"

def get_emoji(change):
    """Получаем эмодзи по изменению цены"""
    if change is None:
        return "❓"
    try:
        change = float(change)
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
    except (TypeError, ValueError):
        return "❓"

def get_fear_greed_emoji(value):
    """Эмодзи для индекса страха/жадности"""
    try:
        value = int(value)
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
    except (TypeError, ValueError):
        return "😐"

def safe_format_price(price):
    """Безопасное форматирование цены"""
    if price is None:
        return "N/A"
    try:
        price = float(price)
        if price < 0.01:
            return f"${price:.8f}"
        elif price < 1:
            return f"${price:.6f}"
        else:
            return f"${price:,.2f}"
    except (TypeError, ValueError):
        return "N/A"

def safe_percent_change(change):
    """Безопасное форматирование процентного изменения"""
    if change is None:
        return "+0.00"
    try:
        change_float = float(change)
        return f"{change_float:+.2f}"
    except (TypeError, ValueError):
        return "+0.00"

async def create_crypto_message():
    try:
        logger.info("Начинаем сбор данных...")
        
        # Получаем все данные
        all_cryptos = await get_crypto_data(100)
        global_data = await get_global_metrics()
        fear_greed = await get_fear_greed_index()
        gold_data = await get_gold_price()
        stocks_data = await get_all_stocks_data()
        
        logger.info(f"Получено криптовалют: {len(all_cryptos) if all_cryptos else 0}")
        logger.info(f"Глобальные данные: {global_data is not None}")
        logger.info(f"Золото: {gold_data is not None}")
        logger.info(f"Акции: {len(stocks_data)}")
        
        if not all_cryptos:
            return "❌ Ошибка при получении данных крипторынка"
        
        # Фильтруем криптовалюты (убираем стейбкоины)
        filtered_cryptos = [c for c in all_cryptos if c.get('symbol') not in STABLE_COINS]
        
        # Находим BTC и ETH
        btc = next((c for c in filtered_cryptos if c.get('symbol') == 'BTC'), None)
        eth = next((c for c in filtered_cryptos if c.get('symbol') == 'ETH'), None)
        
        # Топ роста (исключая BTC и ETH)
        top_gainers = sorted(
            [c for c in filtered_cryptos if c.get('symbol') not in ['BTC', 'ETH']],
            key=lambda x: x.get('quote', {}).get('USD', {}).get('percent_change_24h', 0) or 0,
            reverse=True
        )[:5]
        
        # Топ падения (исключая BTC и ETH)
        top_losers = sorted(
            [c for c in filtered_cryptos if c.get('symbol') not in ['BTC', 'ETH']],
            key=lambda x: x.get('quote', {}).get('USD', {}).get('percent_change_24h', 0) or 0
        )[:5]
        
        message = "🔥 <b>MARVEL MARKET DIGEST</b> 🔥\n\n"
        
        # Глобальная статистика
        if global_data:
            quote = global_data.get('quote', {}).get('USD', {})
            total_cap = quote.get('total_market_cap')
            total_volume = quote.get('total_volume_24h')
            btc_dominance = global_data.get('btc_dominance', 0)
            eth_dominance = global_data.get('eth_dominance', 0)
            
            message += "📊 <b>ОБЗОР РЫНКА</b>\n"
            message += f"• Капитализация: {safe_format_number(total_cap)}\n"
            message += f"• Объем 24ч: {safe_format_number(total_volume)}\n"
            message += f"• Доминирование BTC: {btc_dominance:.1f}%\n"
            message += f"• Доминирование ETH: {eth_dominance:.1f}%\n"
        
        # Индекс страха/жадности
        fg_value = fear_greed.get('value', 50)
        fg_emoji = get_fear_greed_emoji(fg_value)
        message += f"• {fg_emoji} Индекс страха/жадности: <b>{fg_value}</b> ({fear_greed.get('value_classification', 'Neutral')})\n\n"
        
        # Биткоин и Эфир
        message += "👑 <b>ЛИДЕРЫ РЫНКА</b>\n"
        if btc:
            btc_data = btc.get('quote', {}).get('USD', {})
            btc_price = btc_data.get('price', 0)
            btc_change = btc_data.get('percent_change_24h', 0)
            message += f"₿ <b>BITCOIN</b>\n"
            message += f"  {safe_format_price(btc_price)} | "
            message += f"{'🟢' if (btc_change or 0) > 0 else '🔴'} {safe_percent_change(btc_change)}%\n"
        
        if eth:
            eth_data = eth.get('quote', {}).get('USD', {})
            eth_price = eth_data.get('price', 0)
            eth_change = eth_data.get('percent_change_24h', 0)
            message += f"🔷 <b>ETHEREUM</b>\n"
            message += f"  {safe_format_price(eth_price)} | "
            message += f"{'🟢' if (eth_change or 0) > 0 else '🔴'} {safe_percent_change(eth_change)}%\n"
        
        message += "\n"
        
        # Топ роста
        if top_gainers:
            message += "🚀 <b>ТОП РОСТА (24ч)</b>\n"
            for crypto in top_gainers:
                quote = crypto.get('quote', {}).get('USD', {})
                symbol = crypto.get('symbol', 'UNKNOWN')
                price = quote.get('price', 0)
                change = quote.get('percent_change_24h', 0)
                emoji = get_emoji(change)
                message += f"{emoji} <b>{symbol}</b>\n"
                message += f"  {safe_format_price(price)} | 🟢 +{safe_percent_change(change)}%\n"
            message += "\n"
        
        # Топ падения
        if top_losers:
            message += "💀 <b>ТОП ПАДЕНИЯ (24ч)</b>\n"
            for crypto in top_losers:
                quote = crypto.get('quote', {}).get('USD', {})
                symbol = crypto.get('symbol', 'UNKNOWN')
                price = quote.get('price', 0)
                change = quote.get('percent_change_24h', 0)
                emoji = get_emoji(change)
                message += f"{emoji} <b>{symbol}</b>\n"
                message += f"  {safe_format_price(price)} | 🔴 {safe_percent_change(change)}%\n"
            message += "\n"
        
        # Традиционные активы
        message += "💼 <b>ТРАДИЦИОННЫЕ АКТИВЫ</b>\n"
        
        # Золото
        if gold_data:
            gold_quote = gold_data.get('quote', {}).get('USD', {})
            gold_price = gold_quote.get('price', 0)
            gold_change = gold_quote.get('percent_change_24h', 0)
            message += f"🥇 <b>ЗОЛОТО (PAXG)</b>\n"
            message += f"  ${gold_price:,.2f} | "
            message += f"{'🟢' if (gold_change or 0) > 0 else '🔴'} {safe_percent_change(gold_change)}%\n"
        
        # Акции
        if stocks_data:
            for stock_symbol in STOCKS_SYMBOLS:
                if stock_symbol in stocks_data:
                    stock = stocks_data[stock_symbol]
                    stock_price = stock.get('price', 0)
                    stock_change = stock.get('change_percent', 0)
                    if stock_price > 0:  # Проверяем что данные валидные
                        change_emoji = '🟢' if stock_change > 0 else '🔴'
                        message += f"📊 <b>{stock_symbol}</b> | ${stock_price:,.2f} | {change_emoji} {safe_percent_change(stock_change)}%\n"
        
        message += f"\n⏰ Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n"
        message += "\n💎 <b>MarvelMarket</b> - Твой гид в мире инвестиций!"
        
        return message
    
    except Exception as e:
        logger.error(f"Ошибка в create_crypto_message: {e}", exc_info=True)
        return f"❌ Ошибка при формировании отчета: {str(e)}"

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
