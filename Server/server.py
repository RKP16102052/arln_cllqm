import websockets
import asyncio
import json
import validators
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import uuid
import time
import os
import base64
from PIL import Image
import io

from data.__all_models import User, TempUser, Chat
from data import db_session

from cryptography.fernet import Fernet


HOST = '127.0.0.1' # Был "130.12.45.26"
PORT = 8765
EMAIL = 'mizukage.may@mail.ru'
EMAIL_PASS = 'uGj6ZO7yhEZ1uBQrwV1w'
FERNET_KEY = Fernet(b'b1hj9pFchWx8sOZ1oqVN3cOxLSgvcPTPUdhbS_EM5d4=')

CHATS_LOCATION = 'chats'
os.makedirs(CHATS_LOCATION, exist_ok=True)
CHATS_DATA_LOCATION = os.path.join(CHATS_LOCATION, 'data')
os.makedirs(CHATS_DATA_LOCATION, exist_ok=True)
AVATARS_LOCATION = os.path.join(CHATS_LOCATION, 'avatars')
os.makedirs(AVATARS_LOCATION, exist_ok=True)
GROUP_IMAGES_LOCATION = os.path.join(CHATS_LOCATION, 'group_images')
os.makedirs(GROUP_IMAGES_LOCATION, exist_ok=True)
FILES_DIR = os.path.join(CHATS_LOCATION, 'files')
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs('db', exist_ok=True)

FILES_END_FILE = 'files.json'

connected_clients = set()
email_server = "smtp.mail.ru"
CHATS_LOCATION = CHATS_LOCATION.rstrip('/')


def reg_verification(data: dict):
    nickname = data.get('nickname', None)
    email = data.get('email', None)
    password = data.get('password', None)

    if nickname is None or email is None or password is None:
        return {"action": "register", "status": "error", "message": "Неправильный формат"}

    if type(nickname) is not str or type(email) is not str or type(password) is not str:
        return {"action": "register", "status": "error", "message": "Неправильный формат"}

    if not validators.email(email):
        return {"action": "register", "status": "error", "message": "Неправильная почта"}

    session = db_session.create_session()

    if session.query(User).filter(User.name == nickname).all():
        session.close()
        return {"action": "register", "status": "error", "message": "Такое имя пользователя уже занято"}

    if session.query(User).filter(User.email == email).all():
        session.close()
        return {"action": "register", "status": "error", "message": "Пользователь с такой почтой уже зарегистрирован"}

    old_temp = session.query(TempUser).filter(TempUser.email == email).first()
    if old_temp:
        session.delete(old_temp)
        session.commit()

    session.close()

    code = random.randint(100000, 999999)
    die_time = int(time.time()) + 600
    token = uuid.uuid4().hex

    message = MIMEMultipart()
    message["From"] = EMAIL
    message["To"] = email
    message["Subject"] = "Verification code"
    body = f'Ваш код подтверждения: {code}\nЭтот код будет действителен в течение 10 минут.'
    message.attach(MIMEText(body, "plain"))

    send_email(message)

    session = db_session.create_session()

    temp_user = TempUser()
    temp_user.email = email
    temp_user.name = nickname
    temp_user.hashed_password = password
    temp_user.token = token
    temp_user.verification_code = code
    temp_user.die_time = die_time

    session.add(temp_user)
    session.commit()
    session.close()

    return {"action": "register", "status": "OK", "token": token, "message": "Отправка кода подтверждения."}


def fin_reg(data: dict):
    token = data.get('token', None)
    code = data.get('code', None)
    key = data.get('key', None)

    print(f"[DEBUG] fin_reg received: token={token}, code={code}, key={'present' if key else 'None'}")

    if token is None:
        return {"action": "register_verification", "status": "error", "message": "Отсутствует токен"}
    if code is None:
        return {"action": "register_verification", "status": "error", "message": "Отсутствует код"}
    if key is None:
        return {"action": "register_verification", "status": "error", "message": "Отсутствует публичный ключ"}

    session = db_session.create_session()

    temp_user = session.query(TempUser).filter(TempUser.token == token).first()

    print(f"[DEBUG] temp_user found: {temp_user is not None}")

    if temp_user is None:
        session.close()
        return {"action": "register_verification", "status": "error",
                "message": "Сессия истекла или неверный токен. Зарегистрируйтесь заново."}

    try:
        code_int = int(code)
        if temp_user.verification_code != code_int:
            session.close()
            return {"action": "register_verification", "status": "error",
                    "message": f"Неверный код"}
    except (ValueError, TypeError):
        session.close()
        return {"action": "register_verification", "status": "error", "message": "Неверный формат кода"}

    if temp_user.die_time < int(time.time()):
        session.delete(temp_user)
        session.commit()
        session.close()
        return {"action": "register_verification", "status": "error",
                "message": "Код подтверждения истек. Зарегистрируйтесь заново."}

    user = User()
    user.name = temp_user.name
    user.email = temp_user.email
    user.token = temp_user.token
    user.hashed_password = temp_user.hashed_password
    user.public_key = key

    session.delete(temp_user)
    session.add(user)
    session.commit()
    session.close()

    return {"action": "register_verification", "status": "OK", "message": "Успех"}


def login(data: dict):
    email = data.get('email', None)
    password = data.get('password', None)

    if email is None or password is None:
        return {"action": "login", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()
    user = session.query(User).filter(User.email == email).first()

    if user is None:
        session.close()
        return {"action": "login", "status": "error", "message": "Такой пользователь не зарегистрирован"}

    if not user.hashed_password == password:
        session.close()
        return {"action": "login", "status": "error", "message": "Неверный пароль"}

    token = user.token
    session.close()

    return {"action": "login", "status": "OK", "message": "Успех", "token": token}


def create_chat_with_user(data: dict):
    token = data.get('token', None)
    username = data.get('username', None)

    if token is None or username is None:
        return {"action": "create_chat_with_user", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()

    main_user = session.query(User).filter(User.token == token).first()

    if main_user is None:
        session.close()
        return {"action": "create_chat_with_user", "status": "error", "message": "Неверный токен"}

    user = session.query(User).filter(User.name == username).first()

    if user is None:
        session.close()
        return {"action": "create_chat_with_user", "status": "error", "message": "Неверное имя пользователя"}

    members = f'{main_user.id};{user.id}'
    other_members = f'{user.id};{main_user.id}'
    created_by = main_user.id
    is_private = True

    chat = session.query(Chat).filter(Chat.is_private == True, (Chat.members == members) | (Chat.members == other_members)).first()

    if chat is not None:
        session.close()
        return {"action": "create_chat_with_user", "status": "OK", "message": "Чат уже был создан", "id": chat.id}

    chat = Chat()

    chat.members = members
    chat.created_by = created_by
    chat.is_private = is_private

    session.add(chat)
    session.commit()

    if user.chats is None:
        user.chats = str(chat.id)
    else:
        user.chats = ';'.join(user.chats.split(';') + [str(chat.id)])

    if main_user.chats is None:
        main_user.chats = str(chat.id)
    else:
        main_user.chats = ';'.join(main_user.chats.split(';') + [str(chat.id)])

    chat_id = chat.id

    session.commit()
    session.close()

    with open(os.path.join(CHATS_DATA_LOCATION, str(chat_id) + '.json'), 'w', encoding='UTF-8') as file:
        json.dump({'data': []}, file)

    return {"action": "create_chat_with_user", "status": "OK", "message": "Успех", "id": chat_id}


def get_public_key(data: dict):
    token = data.get('token', None)
    username = data.get('username', None)

    if token is None or username is None:
        return {"action": "get_public_key", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()

    user = session.query(User).filter(User.token == token).first()

    if user is None:
        session.close()
        return {"action": "get_public_key", "status": "error", "message": "Неверный токен"}

    public_key = session.query(User).filter(User.name == username).first()

    if public_key is None:
        session.close()
        return {"action": "get_public_key", "status": "error", "message": "Неверное имя пользователя"}

    public_key = public_key.public_key

    session.close()

    return {"action": "get_public_key", "status": "OK", "message": "Успех", "public_key": public_key}


def send_message(data: dict):
    token = data.get('token', None)
    message = data.get('message', None)
    chat_id = data.get('chat_id', None)
    to_username = data.get('to_username', None)

    if token is None or message is None or chat_id is None or to_username is None:
        return {"action": "send_message", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()

    chat = session.query(Chat).filter(Chat.id == chat_id).first()

    if chat is None:
        session.close()
        return {"action": "send_message", "status": "error", "message": "Неверный id чата"}

    members = chat.members

    user1 = session.query(User).filter(User.token == token).first()

    if user1 is None:
        session.close()
        return {"action": "send_message", "status": "error", "message": "Неверный токен"}

    user2 = session.query(User).filter(User.name == to_username).first()

    session.close()

    if user2 is None:
        return {"action": "send_message", "status": "error", "message": "Неверный токен"}

    if str(user1.id) not in members or str(user2.id) not in members:
        return {"action": "send_message", "status": "error", "message": "Недостаточно прав"}

    with open(os.path.join(CHATS_DATA_LOCATION, str(chat_id) + '.json'), 'r', encoding='UTF-8') as file:
        chat_data = json.load(file)

    with open(os.path.join(CHATS_DATA_LOCATION, str(chat_id) + '.json'), 'w', encoding='UTF-8') as file:
        chat_message = {'from': user1.name,
                        'to': user2.token,
                        'type': 'text',
                        'message': message,
                        'time': time.time()}

        chat_data['data'].append(chat_message)

        json.dump(chat_data, file, indent=4)

    return {"action": "send_message", "status": "OK", "message": message, "chat_id": chat_id}


def get_messages(data: dict):
    token = data.get('token', None)
    chat_id = data.get('chat_id', None)
    last_time = data.get('time', None)

    if token is None or chat_id is None:
        return {"action": "get_messages", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()

    user = session.query(User).filter(User.token == token).first()

    if user is None:
        session.close()
        return {"action": "get_messages", "status": "error", "message": "Неверный токен"}

    if str(chat_id) not in user.chats:
        session.close()
        return {"action": "get_messages", "status": "error", "message": "Недостаточно прав"}

    with open(os.path.join(CHATS_DATA_LOCATION, str(chat_id) + '.json'), 'r', encoding='UTF-8') as file:
        chat_data = json.load(file)

    fin = []

    if last_time is None:
        for i in chat_data['data']:
            if i['to'] == token:
                now = {"from": i["from"], "message": i["message"], "time": i["time"], "type": i['type']}

                if now['type'] == 'file':
                    now['file'] = i['file']

                fin.append(now)
    else:
        for i in chat_data['data']:
            if i['to'] == token and i['time'] > last_time:
                now = {"from": i["from"], "message": i["message"], "time": i["time"], "type": i['type']}

                if now['type'] == 'file':
                    now['file'] = i['file']

                fin.append(now)

    session.close()

    return {"action": "get_messages", "status": "OK", "message": "Успех", "chat_id": chat_id, "data": fin}


def get_name(data: dict):
    token = data.get('token', None)

    if token is None:
        return {"action": "get_name", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()

    user = session.query(User).filter(User.token == token).first()

    if user is None:
        session.close()
        return {"action": "get_name", "status": "error", "message": "Неверный токен"}

    name = user.name

    session.close()

    return {"action": "get_name", "status": "OK", "message": "Успех", "name": name}


def get_chats(data: dict):
    token = data.get('token', None)

    if token is None:
        return {"action": "get_chats", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()

    user = session.query(User).filter(User.token == token).first()

    if user is None:
        session.close()
        return {"action": "get_chats", "status": "error", "message": "Неверный токен"}

    chats = user.chats

    if chats is None:
        chats = []
    else:
        chats = list(map(int, chats.split(';')))
    fin = []

    for i in chats:
        chat = session.query(Chat).filter(Chat.id == i).first()

        if chat.is_private:
            second_user_id = int(list(filter(lambda x: str(user.id) != x, chat.members.split(';')))[0])
            name = session.query(User).filter(User.id == second_user_id).first().name
        else:
            name = chat.name

        fin.append({'id': chat.id, 'name': name})

    session.close()

    return {"action": "get_chats", "status": "OK", "message": "Успех", "chats": fin}


def get_members_keys(data: dict):
    token = data.get('token', None)
    chat_id = data.get('chat_id', None)

    if token is None or chat_id is None:
        return {"action": "get_members_keys", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()

    chat = session.query(Chat).filter(Chat.id == chat_id).first()

    if chat is None:
        session.close()
        return {"action": "get_members_keys", "status": "error", "message": "Неверный id чата"}

    members = list(map(int, chat.members.split(';')))

    tokens = []
    fin = []

    for i in members:
        user = session.query(User).filter(User.id == i).first()
        tokens.append(user.token)
        fin.append({user.name: user.public_key})

    session.close()

    if token not in tokens:
        return {"action": "get_members_keys", "status": "error", "message": "Недостаточно прав"}

    return {"action": "get_members_keys", "status": "OK", "message": "Успех", "content": fin, "chat_id": chat_id}


def create_group(data: dict):
    token = data.get('token', None)
    usernames = data.get('usernames', None)
    name = data.get('name', None)

    image = data.get('image', None)

    if token is None or usernames is None or name is None:
        return {"action": "create_group", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()

    main_user = session.query(User).filter(User.token == token).first()

    if main_user is None:
        session.close()
        return {"action": "create_group", "status": "error", "message": "Неверный токен"}

    ids = []

    try:
        for i in usernames:
            user = session.query(User).filter(User.name == i).first()

            if user is not None:
                if user.id == main_user.id:
                    continue

                ids.append(user.id)
    except Exception:
        session.close()
        return {"action": "create_group", "status": "error", "message": "Неверный формат"}

    if not ids:
        session.close()
        return {"action": "create_group", "status": "error", "message": "Все участники не найдены"}

    members = ';'.join(list(map(str, ids)) + [str(main_user.id)])
    created_by = main_user.id
    is_private = False

    chat = Chat()

    chat.members = members
    chat.created_by = created_by
    chat.is_private = is_private
    chat.name = name
    chat.time_image_updated = time.time()

    session.add(chat)
    session.commit()

    if main_user.chats is None:
        main_user.chats = str(chat.id)
    else:
        main_user.chats = ';'.join(main_user.chats.split(';') + [str(chat.id)])

    for i in ids:
        if i == main_user.id:
            continue

        user = session.query(User).filter(User.id == i).first()

        if user.chats is None:
            user.chats = str(chat.id)
        else:
            user.chats = ';'.join(user.chats.split(';') + [str(chat.id)])

    chat_id = chat.id

    session.commit()
    session.close()

    with open(os.path.join(CHATS_DATA_LOCATION, str(chat_id) + '.json'), 'w', encoding='UTF-8') as file:
        json.dump({'data': []}, file)

    image = base64.decodebytes(bytes(image, encoding='ascii'))

    with open(os.path.join(GROUP_IMAGES_LOCATION, str(chat_id) + '.png'), 'wb') as file:
        file.write(image)

    return {"action": "create_group", "status": "OK", "message": "Успех", "id": chat_id}


def upload_avatar(data: dict):
    token = data.get('token', None)
    image = data.get('image', None)

    if token is None or image is None:
        return {"action": "upload_avatar", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()
    user = session.query(User).filter(User.token == token).first()

    if user is None:
        session.close()
        return {"action": "upload_avatar", "status": "error", "message": "Неверный токен"}

    image = base64.decodebytes(bytes(image, encoding='ascii'))

    with open(os.path.join(AVATARS_LOCATION, token + '.png'), 'wb') as file:
        file.write(image)

    user.time_image_updated = time.time()
    session.commit()
    session.close()

    return {"action": "upload_avatar", "status": "OK", "message": "Успех"}


def download_avatar(data: dict):
    username = data.get('username', None)

    last_time = data.get('time', None)

    if username is None:
        return {"action": "download_avatar", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()
    user = session.query(User).filter(User.name == username).first()
    session.close()

    if user is None:
        return {"action": "download_avatar", "status": "error", "message": "Неверное имя пользователя"}

    if user.time_image_updated is None:
        return {"action": "download_avatar", "status": "OK", "message": "Изображение не обновилось"}

    if last_time is not None:
        if user.time_image_updated <= last_time:
            return {"action": "download_avatar", "status": "OK", "message": "Изображение не обновилось", "time": last_time}

    token = user.token
    image_path = os.path.join(AVATARS_LOCATION, token + '.png')

    if not os.path.exists(image_path):
        return {"action": "download_avatar", "status": "error", "message": "Изображение не найдено"}

    image = Image.open(image_path)

    byte_buff = io.BytesIO()

    image.save(byte_buff, format='PNG')

    image = base64.encodebytes(byte_buff.getvalue()).decode('ascii')

    return {"action": "download_avatar", "status": "OK", "message": "Успех", "image": image, "username": username, "time": user.time_image_updated}


def download_chat_image(data: dict):
    token = data.get('token', None)
    chat_id = data.get('chat_id', None)

    last_time = data.get('time', None)

    if token is None or chat_id is None:
        return {"action": "download_chat_image", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()
    user = session.query(User).filter(User.token == token).first()

    if user is None:
        session.close()
        return {"action": "download_chat_image", "status": "error", "message": "Неверный токен"}

    chat = session.query(Chat).filter(Chat.id == chat_id).first()

    if chat is None:
        session.close()
        return {"action": "download_chat_image", "status": "error", "message": "Неверный id чата"}

    if str(user.id) not in chat.members:
        session.close()
        return {"action": "download_chat_image", "status": "error", "message": "Недостаточно прав"}

    if chat.is_private:
        members = list(map(int, chat.members.split(';')))

        if members[0] == user.id:
            second_user = members[1]
        else:
            second_user = members[0]

        user_s = session.query(User).filter(User.id == second_user).first()

        if user_s.time_image_updated is None:
            session.close()
            return {"action": "download_chat_image", "status": "OK", "message": "Изображение не обновилось"}

        if last_time is not None:
            if user_s.time_image_updated <= last_time:
                session.close()
                return {"action": "download_chat_image", "status": "OK", "message": "Изображение не обновилось"}

        token_s = user_s.token
        image_path = os.path.join(AVATARS_LOCATION, token_s + '.png')
        time_image_updated = user_s.time_image_updated
    else:
        time_image_updated = chat.time_image_updated

        if time_image_updated is None:
            session.close()
            return {"action": "download_chat_image", "status": "OK", "message": "Изображение не обновилось"}

        if last_time is not None:
            if time_image_updated <= last_time:
                session.close()
                return {"action": "download_chat_image", "status": "OK", "message": "Изображение не обновилось"}

        image_path = os.path.join(GROUP_IMAGES_LOCATION, str(chat.id) + '.png')

        if not os.path.exists(image_path):
            session.close()
            return {"action": "download_chat_image", "status": "error", "message": "Изображение не найдено"}

    session.close()

    image = Image.open(image_path)

    byte_buff = io.BytesIO()

    image.save(byte_buff, format='PNG')

    image = base64.encodebytes(byte_buff.getvalue()).decode('ascii')

    return {"action": "download_chat_image", "status": "OK", "message": "Успех", "image": image, "chat_id": chat_id, "time": time_image_updated}


def upload_file(data: dict):
    f_data = data.get('data', None)
    name = data.get('name', None)

    mark = data.get('mark', None)
    message = data.get('message', None)
    to_username = data.get('to_username', None)
    fin = data.get('fin', False)

    if f_data is None or name is None:
        return {"action": "upload_file", "status": "error", "message": "Неверный формат"}

    try:
        with open(FILES_END_FILE, 'r') as file:
            content = json.load(file)

        if name in content:
            return {"action": "upload_file", "status": "error", "message": "Недостаточно прав"}
    except Exception:
        pass

    with open(os.path.join(FILES_DIR, name), 'a') as file:
        file.write(f_data)

    if fin:
        try:
            with open(FILES_END_FILE, 'r') as file:
                content = json.load(file)
        except Exception:
            content = []

        content.append(name)

        with open(FILES_END_FILE, 'w') as file:
            json.dump(content, file)

    fin = {"action": "upload_file", "status": "OK", "message": "Успех", "name": name}

    if mark is not None:
        fin['mark'] = mark

    if message is not None:
        fin['message'] = message

    if to_username is not None:
        fin['to_username'] = to_username

    return fin


def download_file(data: dict):
    name = data.get('name', None)

    if name is None:
        return [{"action": "download_file", "status": "error", "message": "Неверный формат"}]

    file_path = os.path.join(FILES_DIR, name)

    if not os.path.exists(file_path):
        return [{"action": "download_file", "status": "error", "message": "Неверное название"}]

    with open(file_path) as file:
        f_data = file.read()

    fin = []

    for i in range(0, len(f_data), 600000):
        cur_fin = f_data[i:i + 600000]
        fin.append({"action": "download_file", "status": "OK", "message": "Успех", "name": name, "data": cur_fin})

    fin[-1]['fin'] = True

    return fin


def send_file(data: dict):
    token = data.get('token', None)
    name = data.get('name', None)
    message = data.get('message', None)
    chat_id = data.get('chat_id', None)
    to_username = data.get('to_username', None)

    if token is None or name is None or chat_id is None or to_username is None or message is None:
        return {"action": "send_file", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()

    chat = session.query(Chat).filter(Chat.id == chat_id).first()

    if chat is None:
        session.close()
        return {"action": "send_file", "status": "error", "message": "Неверный id чата"}

    members = chat.members

    user1 = session.query(User).filter(User.token == token).first()

    if user1 is None:
        session.close()
        return {"action": "send_file", "status": "error", "message": "Неверный токен"}

    user2 = session.query(User).filter(User.name == to_username).first()

    session.close()

    if user2 is None:
        return {"action": "send_file", "status": "error", "message": "Неверный токен"}

    if str(user1.id) not in members or str(user2.id) not in members:
        return {"action": "send_file", "status": "error", "message": "Недостаточно прав"}

    with open(os.path.join(CHATS_DATA_LOCATION, str(chat_id) + '.json'), 'r', encoding='UTF-8') as file:
        chat_data = json.load(file)

    with open(os.path.join(CHATS_DATA_LOCATION, str(chat_id) + '.json'), 'w', encoding='UTF-8') as file:
        chat_message = {'from': user1.name,
                        'to': user2.token,
                        'type': 'file',
                        'message': message,
                        'file': name,
                        'time': time.time()}

        chat_data['data'].append(chat_message)

        json.dump(chat_data, file, indent=4)

    return {"action": "send_file", "status": "OK", "name": name, "chat_id": chat_id}


async def handler(websocket):
    connected_clients.add(websocket)
    try:
        async for raw in websocket:
            if isinstance(raw, str):
                encrypted_data = raw.encode('utf-8')
            elif isinstance(raw, bytes):
                encrypted_data = raw
            else:
                encrypted_data = bytes(raw)

            try:
                decrypted_bytes = FERNET_KEY.decrypt(encrypted_data)
                decrypted = decrypted_bytes.decode('utf-8')

                if decrypted and decrypted[-1] in '\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10':
                    pad_len = ord(decrypted[-1])
                    if 1 <= pad_len <= 16:
                        if all(ord(c) == pad_len for c in decrypted[-pad_len:]):
                            decrypted = decrypted[:-pad_len]

                data = json.loads(decrypted)
                print(f"Received: {data.get('action')} from {websocket.remote_address}")

            except Exception as e:
                print(f"Decryption error: {e}")
                error_response = {"status": "error", "message": f"Decryption failed: {str(e)}"}
                await websocket.send(FERNET_KEY.encrypt(json.dumps(error_response).encode()))
                continue

            action = data.get('action', None)

            if action == 'register':
                response = reg_verification(data)
            elif action == 'register_verification':
                print(f"[DEBUG] Calling fin_reg with data: {data}")
                response = fin_reg(data)
                print(f"[DEBUG] fin_reg response: {response}")
            elif action == 'login':
                response = login(data)
            elif action == 'create_chat_with_user':
                response = create_chat_with_user(data)
            elif action == 'get_public_key':
                response = get_public_key(data)
            elif action == 'send_message':
                response = send_message(data)
            elif action == 'get_messages':
                response = get_messages(data)
            elif action == 'get_name':
                response = get_name(data)
            elif action == 'get_chats':
                response = get_chats(data)
            elif action == 'get_members_keys':
                response = get_members_keys(data)
            elif action == 'create_group':
                response = create_group(data)
            elif action == 'upload_avatar':
                response = upload_avatar(data)
            elif action == 'download_avatar':
                response = download_avatar(data)
            elif action == 'download_chat_image':
                response = download_chat_image(data)
            elif action == 'upload_file':
                response = upload_file(data)
            elif action == 'download_file':
                responses = download_file(data)
                for resp in responses:
                    encrypted_resp = FERNET_KEY.encrypt(json.dumps(resp, ensure_ascii=False).encode())
                    await websocket.send(encrypted_resp.decode())
                continue
            elif action == 'send_file':
                response = send_file(data)
            else:
                response = {"status": "error", "message": "Неизвестное действие"}

            if response:
                try:
                    encrypted_response = FERNET_KEY.encrypt(json.dumps(response, ensure_ascii=False).encode())
                    await websocket.send(encrypted_response.decode())
                except Exception as e:
                    print(f"Response send error: {e}")

    except websockets.exceptions.ConnectionClosed:
        print(f"Connection closed")
    except Exception as e:
        print(f"Handler error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        connected_clients.discard(websocket)


def start_email_server():
    global email_server

    email_server = smtplib.SMTP('smtp.mail.ru', 587)
    email_server.starttls()
    email_server.login(EMAIL, EMAIL_PASS)


def send_email(message: MIMEMultipart):
    try:
        email_server.sendmail(message["From"], message["To"], message.as_string())
    except Exception as e:
        print('Ошибка почтового сервера:', e)
        print('Попытка перезапуска...')

        start_email_server()

        try:
            email_server.sendmail(message["From"], message["To"], message.as_string())
            print('Успех!')
        except Exception:
            print('Неудача.')

# TODO не трогать, поправлю
def delete_chat(data: dict):
    token = data.get('token', None)
    chat_id = data.get('chat_id', None)

    if token is None or chat_id is None:
        return {"action": "delete_chat", "status": "error", "message": "Неверный формат"}

    session = db_session.create_session()
    user = session.query(User).filter(User.token == token).first()

    if user is None:
        session.close()
        return {"action": "delete_chat", "status": "error", "message": "Неверный токен"}

    chat = session.query(Chat).filter(Chat.id == chat_id).first()

    if chat is None:
        session.close()
        return {"action": "delete_chat", "status": "error", "message": "Чат не найден"}

    if chat.created_by != user.id:
        session.close()
        return {"action": "delete_chat", "status": "error", "message": "Только создатель чата может удалить его"}

    messages_file = os.path.join(CHATS_DATA_LOCATION, f"{chat_id}.json")
    if os.path.exists(messages_file):
        os.remove(messages_file)

    group_image = os.path.join(GROUP_IMAGES_LOCATION, f"{chat_id}.png")
    if os.path.exists(group_image):
        os.remove(group_image)

    members = chat.members.split(';')
    for member_id in members:
        member = session.query(User).filter(User.id == int(member_id)).first()
        if member and member.chats:
            chats_list = member.chats.split(';')
            if str(chat_id) in chats_list:
                chats_list.remove(str(chat_id))
                member.chats = ';'.join(chats_list) if chats_list else None
    session.delete(chat)
    session.commit()
    session.close()

    return {"action": "delete_chat", "status": "OK", "message": "Чат удален", "chat_id": chat_id}


async def main():
    db_session.global_init('db/main.db')
    start_email_server()

    async with websockets.serve(handler, HOST, PORT):
        print(f"WS сервер запущен на ws://{HOST}:{PORT}")
        print("Ожидание подключений...")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
