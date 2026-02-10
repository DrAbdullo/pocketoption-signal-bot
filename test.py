from pocketoptionapi.stable_api import PocketOption

# --- Настройки ---
USERNAME = "abdullodoc@yande[.com]"  # обычно email
PASSWORD = "Rimidolv@1980"
DEMO = True  # True → демо-счёт, False → реальный счёт

# --- Создаём клиент ---
client = PocketOption(username=USERNAME, password=PASSWORD, demo=DEMO)

# Подключаемся к серверу
client.connect()

# Проверяем соединение
if client.check_connect():
    print("✅ Успешно подключились к PocketOption")

# Получаем баланс
balance = client.get_balance()
print("Баланс:", balance)

# Закрываем соединение
client.close()
