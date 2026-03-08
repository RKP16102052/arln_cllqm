import json
import asyncio
import websockets
import uuid
from datetime import datetime
import os
import base64
import hashlib
import time

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def save_file(file_data_base64, original_filename):
    file_hash = hashlib.md5(file_data_base64.encode()).hexdigest()[:8]
    timestamp = int(time.time())
    file_id = f"{timestamp}_{file_hash}_{original_filename}"
    file_path = os.path.join(UPLOAD_DIR, file_id)

    with open(file_path, "wb") as f:
        f.write(base64.b64decode(file_data_base64))
    return file_id


def get_file_data(file_id):
    file_path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.exists(file_path):
        return None, None
    with open(file_path, "rb") as f:
        file_data = f.read()
    parts = file_id.split('_', 2)
    if len(parts) == 3:
        original_filename = parts[2]
    else:
        original_filename = file_id  # fallback
    return original_filename, base64.b64encode(file_data).decode('utf-8')

USERS_FILE = "users.json"
MESSAGES_FILE = "messages.json"
connected_clients = set()
message_history = []  # храним сообщения в памяти для быстрого доступа


# -------------------- utils --------------------

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def load_messages():
    """Загружает историю сообщений из файла"""
    global message_history
    if not os.path.exists(MESSAGES_FILE):
        message_history = []
        return []
    try:
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            message_history = json.load(f)
            return message_history
    except Exception as e:
        print(f"Ошибка загрузки истории: {e}")
        message_history = []
        return []


def save_messages():
    """Сохраняет историю сообщений в файл"""
    try:
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(message_history[-1000:], f, ensure_ascii=False, indent=2)  # храним последние 1000 сообщений
    except Exception as e:
        print(f"Ошибка сохранения истории: {e}")


def add_message_to_history(message):
    """Добавляет сообщение в историю и сохраняет"""
    global message_history
    message_history.append(message)
    # Сохраняем каждые 10 сообщений для производительности
    if len(message_history) % 10 == 0:
        save_messages()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def find_user_by_phone(users, phone):
    for u in users:
        if u.get("phone") == phone:
            return u
    return None


def find_user_by_token(token):
    users = load_users()
    for u in users:
        if u.get("token") == token:
            return u
    return None


# -------------------- auth handlers --------------------

def register_user(phone: str, nickname: str, password: str, sms_code: str):
    if not (phone and nickname and password and sms_code):
        return {"status": "error", "message": "Не все поля заполнены"}
    # Заглушка СМС-кода
    if sms_code != "000000":
        return {"status": "error", "message": "Неверный код из SMS"}

    users = load_users()
    if find_user_by_phone(users, phone):
        return {"status": "error", "message": "Пользователь с таким номером уже существует"}

    token = uuid.uuid4().hex
    users.append({
        "phone": phone,
        "nickname": nickname,
        "password_hash": hash_password(password),
        "token": token,
    })
    save_users(users)
    return {"status": "ok", "message": "Регистрация прошла успешно", "token": token, "nickname": nickname}


def login_user(phone: str, password: str):
    users = load_users()
    user = find_user_by_phone(users, phone)
    if not user:
        return {"status": "error", "message": "Пользователь не найден"}
    if user.get("password_hash") != hash_password(password):
        return {"status": "error", "message": "Неверный пароль"}
    # обновим токен на всякий случай
    user["token"] = user.get("token") or uuid.uuid4().hex
    save_users(users)
    return {"status": "ok", "message": "Авторизация успешна", "token": user["token"], "nickname": user["nickname"]}


def auth_by_token(token: str):
    if not token:
        return {"status": "error", "message": "Токен не передан"}
    users = load_users()
    for u in users:
        if u.get("token") == token:
            return {"status": "ok", "nickname": u.get("nickname"), "phone": u.get("phone"), "token": token}
    return {"status": "error", "message": "Неверный токен"}


async def send_history(websocket):
    """Отправляет историю сообщений подключившемуся клиенту"""
    if message_history:
        # Отправляем последние 100 сообщений
        recent_messages = message_history[-100:]
        await websocket.send(json.dumps({
            "type": "history",
            "messages": recent_messages
        }, ensure_ascii=False))


# -------------------- websocket --------------------

async def handler(websocket):
    connected_clients.add(websocket)
    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Пришёл текст без JSON — рассылаем как простой чат
                payload = {
                    "type": "chat",
                    "from": "unknown",
                    "text": str(raw),
                    "ts": datetime.utcnow().isoformat()
                }
                add_message_to_history(payload)
                await broadcast(payload, websocket)
                continue

            action = data.get("action") or data.get("type")

            # --- auth endpoints over WS ---
            if action == "register":
                resp = register_user(
                    data.get("phone"), data.get("nickname"), data.get("password"), data.get("sms_code")
                )
                await websocket.send(json.dumps(resp, ensure_ascii=False))
                if resp.get("status") == "ok":
                    # Отправляем историю после успешной регистрации
                    await send_history(websocket)
                continue

            if action == "login":
                resp = login_user(data.get("phone"), data.get("password"))
                await websocket.send(json.dumps(resp, ensure_ascii=False))
                if resp.get("status") == "ok":
                    # Отправляем историю после успешного входа
                    await send_history(websocket)
                continue

            if action == "token_auth":
                resp = auth_by_token(data.get("token"))
                await websocket.send(json.dumps(resp, ensure_ascii=False))
                if resp.get("status") == "ok":
                    # Отправляем историю после успешной аутентификации по токену
                    await send_history(websocket)
                continue

            # --- chat/file messages ---
            if action == "chat":
                msg = {
                    "type": "chat",
                    "from": data.get("from", "unknown"),
                    "text": data.get("text", ""),
                    "ts": datetime.now().isoformat(),
                }
                # Сохраняем в историю
                add_message_to_history(msg)
                await broadcast(msg, websocket)
                continue

            if action == "file":
                # Сохраняем файл на диск
                file_id = save_file(data.get("data"), data.get("filename"))

                file_msg = {
                    "type": "file",
                    "from": data.get("from", "unknown"),
                    "filename": data.get("filename"),
                    "file_id": file_id,  # вместо data
                    "ts": datetime.now().isoformat(),
                }
                add_message_to_history(file_msg)
                await broadcast(file_msg, websocket)
                continue

            if action == "download":
                file_id = data.get("file_id")
                if not file_id:
                    await websocket.send(json.dumps({"status": "error", "message": "Не указан file_id"}))
                    continue

                filename, file_data = get_file_data(file_id)
                if filename is None:
                    await websocket.send(json.dumps({"status": "error", "message": "Файл не найден"}))
                    continue

                # Отправляем файл клиенту
                response = {
                    "type": "file_download",
                    "filename": filename,
                    "data": file_data,
                    "file_id": file_id
                }
                await websocket.send(json.dumps(response, ensure_ascii=False))
                continue

            await websocket.send(json.dumps({"status": "error", "message": "Неизвестное действие"}, ensure_ascii=False))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)


async def broadcast(message: dict, sender_ws):
    """Расслыает сообщение всем кроме отправителя"""
    dead = []
    for client in connected_clients:
        if client is sender_ws:
            continue
        try:
            await client.send(json.dumps(message, ensure_ascii=False))
        except websockets.exceptions.ConnectionClosed:
            dead.append(client)
    for d in dead:
        connected_clients.discard(d)


async def main():
    # Загружаем историю при старте сервера
    load_messages()
    print(f"Загружено {len(message_history)} сообщений из истории")

    async with websockets.serve(handler, "130.12.45.26", 8765):
        print("WS сервер запущен на ws://130.12.45.26:8765")
        print("Ожидание подключений...")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())