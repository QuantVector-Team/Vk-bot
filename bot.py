import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import requests
from datetime import datetime
import ollama

from config import TOKEN, GROUP_ID, ADMIN_ID, BACKEND_URL

# ================= INIT =================

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

user_states = {}
user_pages = {}
user_data = {}

HEADERS = {
    "User-Agent": "MyBot/1.0",
    "Accept": "application/json"
}

# ================= КЛАВИАТУРЫ =================

def main_keyboard(user_id):
    keyboard = VkKeyboard()

    keyboard.add_button("📊 Запустить анализ", VkKeyboardColor.PRIMARY)
    keyboard.add_button("📜 История тестов", VkKeyboardColor.SECONDARY)
    keyboard.add_line()

    keyboard.add_button("📡 Статус серверов", VkKeyboardColor.POSITIVE)
    keyboard.add_button("❓ Помощь", VkKeyboardColor.SECONDARY)
    keyboard.add_line()

    keyboard.add_button("🛠 Тех. поддержка", VkKeyboardColor.NEGATIVE)

    if user_id == ADMIN_ID:
        keyboard.add_line()
        keyboard.add_button("⚙️ Команды", VkKeyboardColor.POSITIVE)

    return keyboard.get_keyboard()

def back_keyboard():
    keyboard = VkKeyboard()
    keyboard.add_button("⬅️ Назад", VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def history_keyboard(page, total_pages):
    keyboard = VkKeyboard()
    has_arrows = False

    if page > 0:
        keyboard.add_button("⬅️", VkKeyboardColor.SECONDARY)
        has_arrows = True

    if page < total_pages - 1:
        keyboard.add_button("➡️", VkKeyboardColor.SECONDARY)
        has_arrows = True

    if has_arrows:
        keyboard.add_line()

    keyboard.add_button("⬅️ Назад", VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

# ================= SEND =================

def send(user_id, text, keyboard=None):
    vk.messages.send(
        user_id=user_id,
        message=text,
        random_id=0,
        keyboard=keyboard
    )

# ================== AI ==================

def ask_ai(text):
    try:
        system_prompt = (
            "Ты — реальный человек, сотрудник техподдержки сервиса QuantVector. "
            "О компании: QuantVector — это платформа для алгоритмического трейдинга, запуска бектестов и анализа криптовалютного рынка. "
            "ТВОИ СТРОГИЕ ПРАВИЛА: "
            "1. НИКОГДА не говори, что ты искусственный интеллект, нейросеть, бот или ИИ. Ты — живой сотрудник поддержки. "
            "2. Отвечай сразу и по делу. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ пустые вводные фразы вроде 'Здорово, что ты задал вопрос', 'Я рад помочь', 'Я понимаю'. "
            "3. Отвечай кратко, вежливо и строго на русском языке.\n\n"
            f"Вопрос пользователя: {text}\n"
            "Твой ответ:"
        )

        response = ollama.generate(
            model="qwen2.5:1.5b",
            prompt=system_prompt,
            keep_alive="24h"
        )
        return response["response"]
    except Exception as e:
        print("AI ERROR:", e)
        return "⚠️ Ошибка AI. Напишите 'Оператор'"

# ================= ИСТОРИЯ =================

def show_history(user_id):
    page = user_pages.get(user_id, 0)
    per_page = 3 

    try:
        payload = {
            "platform": "vk",
            "token": str(user_id),
            "limit": per_page,
            "offset": page * per_page
        }
        
        response = requests.post(f"{BACKEND_URL}/api/history", json=payload, headers=HEADERS)

        if response.status_code == 200:
            try:
                data_json = response.json()
                
                if data_json.get("status") == "success":
                    data = data_json.get("data", [])
                    
                    if not data and page == 0:
                        send(user_id, "📭 История пуста. Вы еще не запускали бектесты.", main_keyboard(user_id))
                        return
                    
                    total_pages = data_json.get("total_pages", 1) 
                    text = f"📜 История бектестов (стр. {page+1}/{total_pages}):\n\n"

                    for item in data:
                        profit = float(item["profit_percent"])
                        sign = "+" if profit > 0 else ""
                        status_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                        
                        text += (
                            f"📅 {item['date']} | 🪙 {item['symbol']}\n"
                            f"⚙️ Стратегия: {item['strategy_name']}\n"
                            f"{status_emoji} Профит: {sign}{profit}%\n"
                            f"➖➖➖➖➖➖➖➖\n"
                        )

                    send(user_id, text, history_keyboard(page, total_pages))
                
                elif data_json.get("status") == "error":
                    error_msg = data_json.get("message", "Неизвестная ошибка")
                    send(user_id, f"❌ Ошибка: {error_msg}", main_keyboard(user_id))
                else:
                    send(user_id, "❌ Не удалось загрузить историю.", main_keyboard(user_id))
            except Exception as e:
                send(user_id, f"❌ Ошибка чтения ответа: {e}", main_keyboard(user_id))
        else:
            send(user_id, f"❌ Ошибка сервера {response.status_code}.", main_keyboard(user_id))

    except Exception as e:
        send(user_id, f"⚠️ Ошибка сервера: {e}", main_keyboard(user_id))

# ================= START =================

print("Бот запущен...")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.strip()

        # ===== НАЗАД =====
        if text == "⬅️ Назад":
            user_states[user_id] = None
            if user_id in user_data:
                del user_data[user_id]
            send(user_id, "🔙 Возврат в главное меню", main_keyboard(user_id))
            continue

        # ===== РЕГИСТРАЦИЯ =====
        if text.lower() == "начать":
            user_states[user_id] = "WAIT_NAME"
            welcome_msg = (
                "👋 Добро пожаловать в QuantVector — ваш умный помощник для алгоритмического трейдинга!\n\n"
                "Для завершения регистрации, пожалуйста, отправьте ваши Фамилию и Имя одним сообщением (например: Иванов Иван):"
            )
            send(user_id, welcome_msg, back_keyboard())

        # ===== ВВОД ИМЕНИ =====
        elif user_states.get(user_id) == "WAIT_NAME":
            if len(text.split()) < 2:
                send(user_id, "⚠️ Пожалуйста, введите данные корректно: Фамилию и Имя через пробел.", back_keyboard())
                continue
            
            user_name = text 
            send(user_id, "⏳ Секунду, регистрируем ваш профиль...", main_keyboard(user_id))

            try:
                payload = {
                    "platform": "vk",
                    "auth_data": {
                        "vk_user_id": user_id,
                        "login": user_name
                    }
                }
                
                response = requests.post(f"{BACKEND_URL}/api/register", json=payload, headers=HEADERS)

                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("status") == "success":
                        send(user_id, f"✅ Аккаунт успешно привязан!\nДобро пожаловать, {user_name}!", main_keyboard(user_id))
                    elif data.get("status") == "error":
                        error_msg = data.get("message", "Неизвестная ошибка.")
                        send(user_id, f"❌ Ошибка регистрации: {error_msg}", main_keyboard(user_id))
                else:
                    send(user_id, f"❌ Ошибка сервера {response.status_code}.", main_keyboard(user_id))

            except Exception as e:
                send(user_id, f"⚠️ Ошибка связи с сервером: {e}", main_keyboard(user_id))
            
            user_states[user_id] = None

        # ===== АНАЛИЗ =====
        
        elif text == "📊 Запустить анализ":
            user_states[user_id] = "WAIT_SYMBOL"
            user_data[user_id] = {} 
            send(user_id, "1️⃣ Введите тикер монеты для бектеста (например, BTCUSDT):", back_keyboard())

        elif user_states.get(user_id) == "WAIT_SYMBOL":
            user_data[user_id]["symbol"] = text.upper()
            user_states[user_id] = "WAIT_TIMEFRAME"
            send(user_id, "2️⃣ Выберите временной промежуток (например, 15m, 1h, 1d):", back_keyboard())

        elif user_states.get(user_id) == "WAIT_TIMEFRAME":
            user_data[user_id]["timeframe"] = text.lower()
            user_states[user_id] = "WAIT_STRATEGY"
            send(user_id, "3️⃣ Напишите стратегию (RSI или SMA):", back_keyboard())

        elif user_states.get(user_id) == "WAIT_STRATEGY":
            user_input = text.lower()
            symbol = user_data[user_id].get("symbol", "UNKNOWN")
            timeframe = user_data[user_id].get("timeframe", "1h")
            
            if "rsi" in user_input:
                strategy_name = "RSI_Oscillator"
                params = {
                    "period": 14,
                    "buy_level": 30,
                    "sell_level": 70
                }
            elif "sma" in user_input:
                strategy_name = "SMA_Cross"
                params = {
                    "fast_period": 10,
                    "slow_period": 50
                }
            else:
                strategy_name = "RSI_Oscillator"
                params = {"period": 14, "buy_level": 30, "sell_level": 70}

            send(user_id, f"⏳ Сервер проводит бектест:\n🪙 {symbol}\n⏱ {timeframe}\n⚙️ {strategy_name}\n\nОжидайте...", back_keyboard())

            try:
                payload = {
                    "platform": "vk",
                    "vk_user_id": user_id, 
                    "need_chart": False,   
                    "settings": {
                        "symbol": symbol,  
                        "timeframe": timeframe,
                        "start_balance": 1000.0,
                        "fee_percent": 0.1
                    },
                    "strategy": {
                        "name": strategy_name,  
                        "params": params     
                    }
                }
                
                response = requests.post(f"{BACKEND_URL}/api/backtest/run", json=payload, headers=HEADERS)

                if response.status_code == 200:
                    data = response.json()

                    if data.get("status") == "success":
                        summary = data.get("summary", {})
                        profit = float(summary.get("profit_percent", 0.0))
                        sign = "+" if profit > 0 else ""
                        status_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")

                        total_trades = summary.get("total_trades", 0)

                        result = (
                            f"📊 Результат бектеста {symbol}\n"
                            f"⏱ Таймфрейм: {timeframe} | ⚙️ {strategy_name}\n\n"
                            f"{status_emoji} Профит: {sign}{profit}%\n"
                            f"📈 Сделок: {total_trades}\n"
                        )
                    elif data.get("status") == "error":
                        error_msg = data.get("message", "Неизвестная ошибка")
                        result = f"❌ Сервер отклонил бектест.\nПричина: {error_msg}\nОтвет: {data}"
                    else:
                        result = "❌ Неизвестный ответ от сервера."
                else:
                    result = f"❌ Ошибка сервера {response.status_code}."

            except Exception as e:
                result = f"⚠️ Ошибка связи с сервером: {e}"

            send(user_id, result, main_keyboard(user_id))
            
            user_states[user_id] = None
            if user_id in user_data:
                del user_data[user_id]

        # ===== ИСТОРИЯ =====
        elif text == "📜 История тестов":
            user_pages[user_id] = 0
            show_history(user_id)

        elif text == "➡️":
            user_pages[user_id] += 1
            show_history(user_id)

        elif text == "⬅️":
            user_pages[user_id] -= 1
            show_history(user_id)

        # ===== СТАТУС =====
        
        elif text == "📡 Статус серверов":
            send(user_id, "⏳ Проверяем связь с сервером...", back_keyboard())
            try:
                response = requests.get(f"{BACKEND_URL}", timeout=5, headers=HEADERS)

                send(user_id, "🟢 Сервер работает стабильно", main_keyboard(user_id))
            except Exception as e:
                send(user_id, "🔴 Сервер не отвечает", main_keyboard(user_id))

        # ===== ПОМОЩЬ =====
        elif text == "❓ Помощь":
            send(user_id,
                 "📘 Гайд по платформе:\n\n"
                 "📊 Запустить анализ — ввод параметров для бектеста\n"
                 "📜 История тестов — отчеты по вашим запускам\n"
                 "📡 Статус серверов — состояние ИИ-модуля\n"
                 "🛠 Тех. поддержка — связь с ИИ или оператором\n",
                 main_keyboard(user_id))

        # ===== ПОДДЕРЖКА =====
        
        elif text == "🛠 Тех. поддержка":
            user_states[user_id] = "AI_SUPPORT"
            send(user_id, "🤖 Сейчас вы общаетесь с AI-помощником QuantVector.\nПожалуйста, задайте ваш вопрос.\n\n(Если вы хотите связаться с человеком, напишите слово 'Оператор')", back_keyboard())

        elif user_states.get(user_id) == "AI_SUPPORT":
            if text.lower() == "оператор":
                user_states[user_id] = "WAIT_ADMIN"
                send(user_id, "✍️ Опишите вашу проблему, и мы передадим ее специалисту", back_keyboard())
            else:
                send(user_id, "⏳ AI обдумывает ответ. Примерное время ожидания: ~1-2 минуты...", back_keyboard())
                ai_response = ask_ai(text)
                send(user_id, ai_response, back_keyboard())

        elif user_states.get(user_id) == "WAIT_ADMIN":
            vk.messages.send(
                user_id=ADMIN_ID,
                message=f"📩 Пользователь {user_id}:\n{text}",
                random_id=0
            )
            send(user_id, "✅ Отправлено оператору", main_keyboard(user_id))
            user_states[user_id] = None

        # ===== АДМИН =====
        
        elif text == "⚙️ Команды" and user_id == ADMIN_ID:
            send(user_id,
                 "📘 Команды:\n/reply id текст",
                 main_keyboard(user_id))

        elif user_id == ADMIN_ID and text.startswith("/reply"):
            try:
                _, uid, msg = text.split(" ", 2)
                send(int(uid), f"📩 Поддержка:\n{msg}")
                send(user_id, "✅ Ответ отправлен")
            except:
                send(user_id, "❌ Формат: /reply user_id текст")

        # ===== FALLBACK =====
        
        else:
            send(user_id, "❓ Для возврата в меню нажмите 'Назад' или напишите 'Начать'", main_keyboard(user_id))