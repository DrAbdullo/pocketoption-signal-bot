import socket
import asyncio
import websockets

# Список регионов PocketOption
REGIONS = {
    "SERVER2": "wss://api.po.market/socket.io/?EIO=4&transport=websocket",
    "INDIA": "wss://api-in.po.market/socket.io/?EIO=4&transport=websocket",
    "FRANCE": "wss://api-fr.po.market/socket.io/?EIO=4&transport=websocket",
    "FINLAND": "wss://api-fin.po.market/socket.io/?EIO=4&transport=websocket",
    "SERVER3": "wss://api-c.po.market/socket.io/?EIO=4&transport=websocket",
    "ASIA": "wss://api-asia.po.market/socket.io/?EIO=4&transport=websocket",
}

# Проверка hosts
def check_hosts_block():
    blocked = []
    with open(r"C:\Windows\System32\drivers\etc\hosts", "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
            for region in ["po.market", "api-in.po.market", "api-fr.po.market",
                           "api-fin.po.market", "api-asia.po.market", "api-c.po.market"]:
                if region in line and not line.strip().startswith("#"):
                    blocked.append(line.strip())
    return blocked

# Проверка DNS
def check_dns(domain):
    try:
        ip = socket.gethostbyname(domain)
        return ip
    except Exception as e:
        return f"Ошибка: {e}"

# Проверка WebSocket
async def check_ws(url):
    try:
        async with websockets.connect(url, ping_timeout=5, close_timeout=5):
            return True
    except Exception as e:
        return f"Ошибка: {e}"

async def main():
    print("🔹 Проверка hosts...")
    blocked_hosts = check_hosts_block()
    if blocked_hosts:
        print("Найдены блокировки в hosts:")
        for line in blocked_hosts:
            print(" ", line)
    else:
        print("hosts чистый для PocketOption")

    print("\n🔹 Проверка DNS...")
    for region, url in REGIONS.items():
        host = url.split("//")[1].split("/")[0]
        ip = check_dns(host)
        print(f"{region}: {host} → {ip}")

    print("\n🔹 Проверка WebSocket...")
    for region, url in REGIONS.items():
        result = await check_ws(url)
        print(f"{region}: {result}")

if __name__ == "__main__":
    asyncio.run(main())
