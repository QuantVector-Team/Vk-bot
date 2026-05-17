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

def timeframe_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("1h", VkKeyboardColor.PRIMARY)
    keyboard.add_button("1d", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("1w", VkKeyboardColor.PRIMARY)
    keyboard.add_button("1m", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def strategy_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("SMA Cross", VkKeyboardColor.PRIMARY)
    keyboard.add_button("RSI Oscillator", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Bollinger Bands", VkKeyboardColor.PRIMARY)
    keyboard.add_button("MACD", VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", VkKeyboardColor.NEGATIVE)
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
            "vk_user_id": str(user_id), # [cite: 730]
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
                        # Безопасное чтение ключей
                        date_str = item.get('date', 'Неизвестная дата')
                        symbol = item.get('symbol', item.get('coin', 'UNKNOWN'))
                        strategy_name = item.get('strategy_name', item.get('strategy', 'Неизвестная стратегия'))
                        profit = float(item.get("profit_percent", 0.0))
                        
                        sign = "+" if profit > 0 else ""
                        status_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                        
                        text += (
                            f"📅 {date_str} | 🪙 {symbol}\n"
                            f"⚙️ Стратегия: {strategy_name}\n"
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

        # ===== АНАЛИЗ (ПОШАГОВЫЙ ВВОД) =====
        elif text == "📊 Запустить анализ":
            user_states[user_id] = "WAIT_SYMBOL"
            user_data[user_id] = {}
            send(user_id, "1️⃣ Введите тикер монеты для бектеста (например, BTCUSDT):", back_keyboard())

        elif user_states.get(user_id) == "WAIT_SYMBOL":
            user_data[user_id]["symbol"] = text.upper()
            user_states[user_id] = "WAIT_TIMEFRAME"
            send(user_id, "2️⃣ Выберите временной промежуток (нажмите кнопку ниже):", timeframe_keyboard())

        elif user_states.get(user_id) == "WAIT_TIMEFRAME":
            user_data[user_id]["timeframe"] = text
            user_states[user_id] = "WAIT_STRATEGY"
            send(user_id, "3️⃣ Выберите стратегию для тестирования:", strategy_keyboard())

        elif user_states.get(user_id) == "WAIT_STRATEGY":
            user_input = text.lower()
            
            # Маппинг стратегий на серверные названия и параметры
            strat_map = {
                "sma cross": "SMA_Cross", # [cite: 737]
                "rsi oscillator": "RSI_Oscillator", # [cite: 740]
                "bollinger bands": "Bollinger_Bands", # [cite: 739]
                "macd": "MACD" # [cite: 742]
            }
            
            strat_name = None
            for key, val in strat_map.items():
                if key in user_input:
                    strat_name = val
                    break
                    
            if not strat_name:
                send(user_id, "⚠️ Пожалуйста, выберите стратегию с помощью кнопок ниже:", strategy_keyboard())
                continue
                
            user_data[user_id]["strategy_name"] = strat_name
            user_data[user_id]["params"] = {}
            
            # Настройка очереди параметров, которые нужно запросить
            if strat_name == "SMA_Cross": # [cite: 737]
                user_data[user_id]["expected_params"] = [
                    ("fast_period", "Быстрый период (от 5 до 50)", int),
                    ("slow_period", "Медленный период (от 50 до 200)", int)
                ]
            elif strat_name == "Bollinger_Bands": # [cite: 739]
                user_data[user_id]["expected_params"] = [
                    ("window", "Размер окна (от 10 до 100)", int),
                    ("deviation", "Отклонение (от 1.0 до 3.0, обязательно с точкой)", float)
                ]
            elif strat_name == "RSI_Oscillator": # [cite: 740]
                user_data[user_id]["expected_params"] = [
                    ("period", "Период (от 5 до 30)", int),
                    ("buy_level", "Уровень покупки (от 10 до 40)", int),
                    ("sell_level", "Уровень продажи (от 60 до 90)", int)
                ]
            elif strat_name == "MACD": # [cite: 742]
                user_data[user_id]["expected_params"] = [
                    ("fast_period", "Быструю EMA (от 5 до 50)", int),
                    ("slow_period", "Медленную EMA (от 20 до 100)", int),
                    ("signal_period", "Сигнальную линию (от 5 до 30)", int)
                ]

            user_states[user_id] = "WAIT_PARAMS"
            next_param = user_data[user_id]["expected_params"][0]
            send(user_id, f"Выбрана стратегия {strat_name}.\n\nВведите {next_param[1]}:", back_keyboard())

        # ===== ВВОД ПАРАМЕТРОВ СТРАТЕГИИ =====
        elif user_states.get(user_id) == "WAIT_PARAMS":
            expected = user_data[user_id]["expected_params"]
            current_param = expected[0]
            
            param_key = current_param[0]
            param_prompt = current_param[1]
            param_type = current_param[2]
            
            try:
                # Преобразуем введенный текст в нужный формат (int или float)
                if param_type == float:
                    val = float(text.replace(',', '.'))
                else:
                    val = int(text)
                    
                # Сохраняем параметр и удаляем его из очереди
                user_data[user_id]["params"][param_key] = val
                user_data[user_id]["expected_params"].pop(0)
                
            except ValueError:
                send(user_id, f"⚠️ Неверный формат! Пожалуйста, введите число.\n\nВведите {param_prompt}:", back_keyboard())
                continue
                
            # Если еще остались параметры — спрашиваем следующий
            if user_data[user_id]["expected_params"]:
                next_param = user_data[user_id]["expected_params"][0]
                send(user_id, f"Введите {next_param[1]}:", back_keyboard())
            else:
                # Все параметры собраны, отправляем запрос!
                symbol = user_data[user_id].get("symbol", "UNKNOWN")
                timeframe = user_data[user_id].get("timeframe", "1h")
                strategy_name = user_data[user_id].get("strategy_name")
                params = user_data[user_id].get("params", {})
                
                send(user_id, f"⏳ Сервер проводит бектест:\n🪙 {symbol}\n⏱ {timeframe}\n⚙️ {strategy_name}\n\nОжидайте...", main_keyboard(user_id))
                
                try:
                    payload = {
                        "platform": "vk",
                        "vk_user_id": str(user_id), # [cite: 730]
                        "need_chart": False,
                        "settings": {
                            "symbol": symbol, # [cite: 803]
                            "timeframe": timeframe,
                            "start_balance": 1000.0,
                            "fee_percent": 0.1
                        },
                        "strategy": {
                            "name": strategy_name, # [cite: 804]
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