import os
import asyncio
import aiohttp
import random
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from aiohttp import web

# ================ НАСТРОЙКИ ================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')  # Изменено!
CHANNEL_ID = os.environ.get('CHANNEL_ID')
CMC_API_KEY = os.environ.get('CMC_API_KEY')
PORT = int(os.environ.get('PORT', 10000))

# ================ API URLs ================
CMC_CRYPTO_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
CMC_GLOBAL_URL = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
CMC_FEAR_GREED_URL = "https://api.alternative.me/fng/"

previous_data = {
    'total_cap': None,
    'btc_price': None,
    'eth_price': None,
    'fear_greed': None,
    'top_gainer': None,
    'top_loser': None
}

# ================ ФУНКЦИИ ================

async def get_market_data():
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            CMC_CRYPTO_URL, 
            headers=headers, 
            params={'limit': 50, 'convert': 'USD'}
        ) as response:
            cryptos = await response.json()
        
        async with session.get(CMC_GLOBAL_URL, headers=headers) as response:
            global_metrics = await response.json()
        
        async with session.get(CMC_FEAR_GREED_URL) as response:
            fear_greed = await response.json()
    
    return {
        'cryptos': cryptos['data'],
        'global': global_metrics['data'],
        'fear_greed': fear_greed['data'][0]
    }

def analyze_market_sentiment(data):
    global_data = data['global']
    cryptos = data['cryptos']
    fg_value = int(data['fear_greed']['value'])
    
    sorted_by_change = sorted(cryptos[:20], key=lambda x: x['quote']['USD']['percent_change_24h'])
    top_loser = sorted_by_change[0]
    top_gainer = sorted_by_change[-1]
    
    positive = sum(1 for c in cryptos[:20] if c['quote']['USD']['percent_change_24h'] > 0)
    negative = 20 - positive
    
    btc = next(c for c in cryptos if c['symbol'] == 'BTC')
    eth = next(c for c in cryptos if c['symbol'] == 'ETH')
    
    return {
        'total_cap': global_data['quote']['USD']['total_market_cap'],
        'cap_change': global_data['quote']['USD']['total_market_cap_yesterday_percentage_change'],
        'btc_price': btc['quote']['USD']['price'],
        'btc_change': btc['quote']['USD']['percent_change_24h'],
        'eth_price': eth['quote']['USD']['price'],
        'eth_change': eth['quote']['USD']['percent_change_24h'],
        'fear_greed': fg_value,
        'top_gainer': top_gainer,
        'top_loser': top_loser,
        'positive_count': positive,
        'negative_count': negative
    }

def generate_digest(current, previous):
    intros = [
        "🔍 <b>Что происходит на рынке?</b>\n\n",
        "📰 <b>Анализ рынка за последний час</b>\n\n",
        "⚡️ <b>Краткий дайджест</b>\n\n",
        "🎯 <b>Обзор движений рынка</b>\n\n"
    ]
    
    message = random.choice(intros)
    
    cap_change = current['cap_change']
    if cap_change > 2:
        message += f"🚀 Рынок ракетой летит вверх! Капитализация выросла на {cap_change:.2f}%. "
        message += "Быки контролируют ситуацию.\n\n"
    elif cap_change > 0.5:
        message += f"📈 Рынок уверенно растёт (+{cap_change:.2f}%). Медленно, но верно движемся наверх.\n\n"
    elif cap_change > -0.5:
        message += f"😐 Рынок в боковике. Изменение всего {cap_change:+.2f}%. Ждём движения.\n\n"
    elif cap_change > -2:
        message += f"📉 Небольшая коррекция {cap_change:.2f}%. Ничего страшного, это здоровое движение.\n\n"
    else:
        message += f"💀 Резкое падение на {cap_change:.2f}%! Паника на рынке продолжается. Медведи атакуют!\n\n"
    
    btc_change = current['btc_change']
    message += f"🟠 <b>Bitcoin:</b> ${current['btc_price']:,.0f} ({btc_change:+.2f}%)\n"
    
    if previous['btc_price']:
        btc_diff = current['btc_price'] - previous['btc_price']
        if abs(btc_diff) > 1000:
            direction = "вырос" if btc_diff > 0 else "упал"
            message += f"   └ {direction} на ${abs(btc_diff):,.0f} за час\n"
    
    eth_change = current['eth_change']
    message += f"🔷 <b>Ethereum:</b> ${current['eth_price']:,.0f} ({eth_change:+.2f}%)\n\n"
    
    if previous['eth_price']:
        eth_diff = current['eth_price'] - previous['eth_price']
        if abs(eth_diff) > 50:
            direction = "вырос" if eth_diff > 0 else "упал"
            message += f"   └ {direction} на ${abs(eth_diff):,.0f} за час\n\n"
    
    fg = current['fear_greed']
    if fg < 25:
        message += f"😱 <b>Индекс страха:</b> {fg} - экстремальный страх! Время покупать?\n\n"
    elif fg < 45:
        message += f"😰 <b>Индекс страха:</b> {fg} - рынок боится. Будьте осторожны.\n\n"
    elif fg < 55:
        message += f"😐 <b>Индекс нейтральный:</b> {fg} - рынок в раздумьях.\n\n"
    elif fg < 75:
        message += f"😊 <b>Индекс жадности:</b> {fg} - оптимизм растёт!\n\n"
    else:
        message += f"🤑 <b>Экстремальная жадность:</b> {fg} - все эйфоричны. Осторожно, возможна коррекция!\n\n"
    
    gainer = current['top_gainer']
    loser = current['top_loser']
    
    message += "━━━━━━━━━━━━━━━━━━\n\n"
    message += f"🔥 <b>Лидер роста:</b> {gainer['symbol']} (+{gainer['quote']['USD']['percent_change_24h']:.2f}%)\n"
    message += f"❄️ <b>Лидер падения:</b> {loser['symbol']} ({loser['quote']['USD']['percent_change_24h']:.2f}%)\n\n"
    
    pos = current['positive_count']
    neg = current['negative_count']
    
    if pos > neg * 1.5:
        message += f"✅ В топ-20: {pos} монет растут, {neg} падают. Рынок в зелёной зоне!\n\n"
    elif neg > pos * 1.5:
        message += f"❌ В топ-20: {neg} монет падают, {pos} растут. Красное море продолжается.\n\n"
    else:
        message += f"⚖️ В топ-20: {pos} растут, {neg} падают. Смешанные настроения.\n\n"
    
    insights = [
        "💡 <i>Помните: волатильность - это возможность!</i>",
        "⚠️ <i>Не торгуйте на эмоциях, следуйте своей стратегии.</i>",
        "🎯 <i>Лучшие входы - когда все боятся.</i>",
        "📊 <i>Следите за объёмами, а не только за ценой.</i>",
        "🧠 <i>Умные деньги покупают страх и продают жадность.</i>",
        "⏰ <i>Терпение - главный навык трейдера.</i>"
    ]
    
    message += random.choice(insights) + "\n\n"
    message += f"⏰ {datetime.now().strftime('%H:%M')} UTC | 💎 <b>MarvelMarket</b>"
    
    return message

async def post_digest():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    global previous_data
    
    while True:
        try:
            delay = random.randint(1800, 5400)
            await asyncio.sleep(delay)
            
            data = await get_market_data()
            current = analyze_market_sentiment(data)
            
            digest = generate_digest(current, previous_data)
            
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=digest,
                parse_mode=ParseMode.HTML
            )
            
            print(f"✅ Дайджест отправлен: {datetime.now()}")
            
            previous_data = current.copy()
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await asyncio.sleep(300)

async def health_check(request):
    return web.Response(text="🚀 MarvelMarket Analyst Bot is running!")

async def start_http_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"🌐 HTTP сервер запущен на порту {PORT}")

async def main():
    await start_http_server()
    print("🚀 MarvelMarket Analyst Bot запущен!")
    await post_digest()

if __name__ == "__main__":
    asyncio.run(main())
