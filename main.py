import asyncio
import time
import requests  # Добавлен для будущего использования ИИ
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from pocketoptionapi_async.client import AsyncPocketOptionClient as PocketOption

# ────────────────────────────────────────────────
# НАСТРОЙКИ — ЗАМЕНИ НА СВОИ
# ────────────────────────────────────────────────

TELEGRAM_TOKEN = "7585332890:AAENVuulaujJ3IWatU7D_L6fsMFg5gvxst4"   # от @BotFather
ALLOWED_USERS = [1604681369]                                     # твой Telegram ID

SSID = 42["auth",{"sessionToken":"a1195110ede8da751daea817fe04416b","uid":"119544254","lang":"ru","currentUrl":"cabinet/demo-quick-high-low","isChart":1}]  # Твой SSID из скриншота

po = PocketOption(ssid=SSID, is_demo=False)  # False — реальный, True — демо

# Группы активов (OTC-версии)
ASSET_GROUPS = {
    "Валюты OTC": [
        "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC",
        "USDCAD-OTC", "NZDUSD-OTC", "EURGBP-OTC", "EURJPY-OTC"
    ],
    "Криптовалюты OTC": [
        "BTC-OTC", "ETH-OTC", "BNB-OTC", "XRP-OTC", "ADA-OTC", "SOL-OTC"
    ],
    "Акции OTC": [
        "APPLE-OTC", "TESLA-OTC", "NVIDIA-OTC", "AMAZON-OTC", "GOOGLE-OTC",
        "MICROSOFT-OTC", "META-OTC"
    ],
    "Индексы OTC": [
        "US30-OTC", "US100-OTC", "US500-OTC", "DE40-OTC", "JP225-OTC"
    ],
    "Товары OTC": [
        "GOLD-OTC", "SILVER-OTC", "OIL-OTC", "NATURALGAS-OTC"
    ]
}

# ────────────────────────────────────────────────
# ФУНКЦИЯ ПРИНЯТИЯ РЕШЕНИЯ (5+1 индикатор + MTF)
# ────────────────────────────────────────────────

async def should_buy(candles_1m, candles_5m=None):
    if len(candles_1m) < 40:
        return None

    closes = [c['close'] for c in candles_1m]
    opens  = [c['open']  for c in candles_1m]
    highs  = [c['high']  for c in candles_1m]
    lows   = [c['low']   for c in candles_1m]

    # 1. 3 свечи подряд одного цвета
    last3_up   = all(closes[i] > opens[i] for i in range(-3, 0))
    last3_down = all(closes[i] < opens[i] for i in range(-3, 0))
    ind1_call = last3_up
    ind1_put  = last3_down

    # 2. RSI(14)
    def rsi(prices, period=14):
        if len(prices) < period + 1:
            return 50
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gain = sum(d for d in deltas[-period:] if d > 0) / period
        loss = sum(-d for d in deltas[-period:] if d < 0) / period or 0.0001
        rs = gain / loss
        return 100 - 100 / (1 + rs)

    rsi_val = rsi(closes)
    ind2_call = rsi_val < 42
    ind2_put  = rsi_val > 58

    # 3. Stochastic %K(14)
    period_k = 14
    lowest_low  = min(lows[-period_k:])
    highest_high = max(highs[-period_k:])
    stoch_k = 100 * (closes[-1] - lowest_low) / (highest_high - lowest_low) if highest_high != lowest_low else 50
    ind3_call = stoch_k < 28
    ind3_put  = stoch_k > 72

    # 4. MACD (исправленный расчёт)
    def ema(prices, n):
        if len(prices) < n:
            return sum(prices) / len(prices)
        alpha = 2 / (n + 1)
        v = prices[-n]
        for p in prices[-n+1:]:
            v = alpha * p + (1 - alpha) * v
        return v

    # Считаем MACD-линию по всей доступной истории
    macd_lines = []
    for i in range(26, len(closes) + 1):
        slice_closes = closes[:i]
        ema12 = ema(slice_closes, 12)
        ema26 = ema(slice_closes, 26)
        macd_lines.append(ema12 - ema26)

    if len(macd_lines) < 9:
        macd_line = 0.0
        macd_signal = 0.0
        macd_hist = 0.0
    else:
        macd_line = macd_lines[-1]
        macd_signal = ema(macd_lines[-9:], 9)  # Правильная EMA9 по последним 9 значениям MACD-линии
        macd_hist = macd_line - macd_signal

    ind4_call = macd_line > 0
    ind4_put  = macd_line < 0

    # 5. Цена относительно EMA34
    ema34 = ema(closes, 34)
    ind5_call = closes[-1] > ema34
    ind5_put  = closes[-1] < ema34

    # 6. ADX (14)
    def adx(highs, lows, closes, period=14):
        if len(highs) < period + 1:
            return 20.0

        dm_plus = [max(highs[i] - highs[i-1], 0) if highs[i] - highs[i-1] > lows[i-1] - lows[i] else 0 for i in range(1, len(highs))]
        dm_minus = [max(lows[i-1] - lows[i], 0) if lows[i-1] - lows[i] > highs[i] - highs[i-1] else 0 for i in range(1, len(lows))]

        tr = [max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])) for i in range(1, len(highs))]

        atr = ema(tr[-period:], period)
        di_plus = 100 * ema(dm_plus[-period:], period) / atr if atr != 0 else 0
        di_minus = 100 * ema(dm_minus[-period:], period) / atr if atr != 0 else 0

        dx = abs(di_plus - di_minus) / (di_plus + di_minus) * 100 if (di_plus + di_minus) != 0 else 0
        adx_val = ema([dx] * period, period)

        return adx_val

    adx_val = adx(highs, lows, closes)
    ind6_call = adx_val > 25
    ind6_put  = adx_val > 25

    # Подсчёт голосов (6 индикаторов)
    call_votes = sum([ind1_call, ind2_call, ind3_call, ind4_call, ind5_call, ind6_call])
    put_votes  = sum([ind1_put,  ind2_put,  ind3_put,  ind4_put,  ind5_put,  ind6_put])

    # MTF-фильтр (5m свеча)
    mtf_ok_call = True
    mtf_ok_put  = True
    if candles_5m and len(candles_5m) >= 1:
        last_5m = candles_5m[-1]
        mtf_up = last_5m['close'] > last_5m['open']
        mtf_ok_call = mtf_up
        mtf_ok_put  = not mtf_up

    # Решение — минимум 5 из 6
    if call_votes >= 5 and mtf_ok_call:
        indicators = []
        if ind1_call: indicators.append("3 зелёные")
        if ind2_call: indicators.append("RSI <42")
        if ind3_call: indicators.append("Stoch <28")
        if ind4_call: indicators.append("MACD >0")
        if ind5_call: indicators.append("выше EMA34")
        if ind6_call: indicators.append(f"ADX {adx_val:.1f} > 25")
        return "call", call_votes, indicators

    if put_votes >= 5 and mtf_ok_put:
        indicators = []
        if ind1_put: indicators.append("3 красные")
        if ind2_put: indicators.append("RSI >58")
        if ind3_put: indicators.append("Stoch >72")
        if ind4_put: indicators.append("MACD <0")
        if ind5_put: indicators.append("ниже EMA34")
        if ind6_put: indicators.append(f"ADX {adx_val:.1f} > 25")
        return "put", put_votes, indicators

    return None

# ────────────────────────────────────────────────
# TELEGRAM-ХЕНДЛЕРЫ
# ────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("Доступ запрещён.")
        return

    keyboard = []
    for group_name in ASSET_GROUPS:
        keyboard.append([InlineKeyboardButton(group_name, callback_data=f"group:{group_name}")])

    keyboard.append([InlineKeyboardButton("🛑 Stop / Остановить бота", callback_data="stop_bot")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите группу активов:", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("group:"):
        group_name = data.split(":", 1)[1]
        if group_name not in ASSET_GROUPS:
            await query.edit_message_text("Группа не найдена.")
            return

        keyboard = []
        for asset in ASSET_GROUPS[group_name]:
            keyboard.append([InlineKeyboardButton(asset, callback_data=f"asset:{asset}")])

        keyboard.append([InlineKeyboardButton("← Назад к группам", callback_data="back_to_groups")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Выберите пару в группе '{group_name}':", reply_markup=reply_markup)
        return

    if data.startswith("asset:"):
        asset = data.split(":", 1)[1]

        found = any(asset in assets for assets in ASSET_GROUPS.values())
        if not found:
            await query.edit_message_text("Пара не найдена.")
            return

        try:
            if not po.is_connected:
                await po.connect()

            candles_1m = await po.get_candles(asset, 60, 100)
            candles_5m = await po.get_candles(asset, 300, 10)
        except Exception as e:
            await query.edit_message_text(f"Ошибка получения свечей: {str(e)}")
            return

        result = await should_buy(candles_1m, candles_5m)

        if result:
            direction, count, ind_list = result
            ind_text = ", ".join(ind_list) if ind_list else "—"

            text = (
                f"📊 Сигнал\n"
                f"Пара: {asset}\n"
                f"Направление: {'CALL ☝️' if direction == 'call' else 'PUT 👇'}\n"
                f"Согласование: {count}/6 индикаторов\n"
                f"Индикаторы: {ind_text}\n"
                f"Экспирация: 1–5 минут (рекомендую 2–3)\n"
                f"Время: {time.strftime('%H:%M:%S')}"
            )
            await query.edit_message_text(text)
        else:
            await query.edit_message_text(f"Сигнала по {asset} сейчас нет (менее 5 индикаторов согласны)")
        return

    if data == "back_to_groups":
        keyboard = []
        for group_name in ASSET_GROUPS:
            keyboard.append([InlineKeyboardButton(group_name, callback_data=f"group:{group_name}")])

        keyboard.append([InlineKeyboardButton("🛑 Stop / Остановить бота", callback_data="stop_bot")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите группу активов:", reply_markup=reply_markup)
        return

    if data == "stop_bot":
        await query.edit_message_text("Бот останавливается...")
        await context.application.stop()
        await context.application.shutdown()
        print("Бот остановлен по команде пользователя")
        return


async def on_startup(app: Application):
    try:
        print("Подключение к PocketOption...")
        await po.connect()
        print("Подключение к PocketOption завершено")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")


# ────────────────────────────────────────────────
# ЗАПУСК
# ────────────────────────────────────────────────

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.post_init = on_startup

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Бот запущен...")
    try:
        application.run_polling()
    except Exception as e:
        print(f"Telegram polling error: {e}")


if __name__ == "__main__":
    main()