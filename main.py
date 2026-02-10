import asyncio
from pocketoptionapi_async.client import AsyncPocketOptionClient as PocketOption

SSID = "oe7urngbessnpfs3kaseodmof0"

async def test():
    po = PocketOption(ssid=SSID, is_demo=False)
    try:
        await po.connect()
        print("Успешно подключено!")
        print("Баланс:", await po.get_balance())
    except Exception as e:
        print("Ошибка:", e)

asyncio.run(test())