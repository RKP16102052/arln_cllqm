import websocket
import json
import threading
import time
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet
import base64


HOST = '127.0.0.1' # Был "130.12.45.26" 
PORT = 8765 
TOKEN_FILE = 'token'

WEBSOCKET_URL = f"ws://{HOST}:{PORT}"
FERNET_KEY = Fernet(b'b1hj9pFchWx8sOZ1oqVN3cOxLSgvcPTPUdhbS_EM5d4=')


class Test:
    def __init__(self):
        self.token = None
        ws_thread = threading.Thread(target=self.run_websocket, daemon=True, )
        ws_thread.start()
        time.sleep(1)
        # self.register() # Регистрация.
        # self.login() # Вход.
        # self.get_public_key()
        # print(self.make_public_key())
        # self.get_public_key()
        self.send_message('''-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAj2AAefgLoEuJwcX8ZvMH
f2I5cvZU8HLZzsK4ghAgIdaGqY+mk8FVq7y4FMPI4G2gyMcnUqRhazv2VJ4KiuZu
/pRClP0HJIOTH60u+M90jIyq56QaJVjds+ON5OtQxZam+1vGgILD35CAi0XjGU+M
7bJ7OPjjBFOtsb0eQisabOHmf/dJWBd5wHjw+20jB9jAb1kXueYZaZSAKTdxQhcA
AlyjlMT2Pj6JtFaPMI8TF7K2SfZLQodBUQ6AP2zRmWnB4dxgo6jK1VWgkAE0GfdX
W24eUYw9p36zEToB4O5/gitQXKXq3UIlwdUM3Qaau2KH8pQVcWIvAMUxMY1m9lxQ
/QIDAQAB
-----END PUBLIC KEY-----
''')
        # self.get_messages()
        # self.get_chats()
        ws_thread.join()

    def on_ws_message(self, ws, message):
        data = json.loads(FERNET_KEY.decrypt(message).decode())
        print(data)
        action = data.get('action')

        if (action == 'register' and data['status'] == 'OK') or (action == 'register_verification' and data["message"] == "Неверный код"):
            self.token = data.get('token', self.token)
            code = int(input('Введите код подтверждения: '))
            key = self.make_public_key()

            data = {
                "action": "register_verification",
                "token": self.token,
                'code': code,
                "key": key
            }
            self.send_to_websocket(data)
        elif action == 'login' and data['status'] == 'OK':
            ...
        elif action == 'get_public_key':
            self.send_message(data['public_key'])
        elif action == 'get_messages':
            key = self.get_private_key()
            print(key)

            for i in data['data']:
                message = key.decrypt(
                    base64.decodebytes(i['message'].encode('ascii')),
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                print(message.decode())

    def run_websocket(self):
        try:
            self.ws = websocket.WebSocketApp(
                WEBSOCKET_URL,
                on_message=self.on_ws_message
            )
            self.ws.run_forever()
        except Exception as e:
            print("Ошибка подключения WebSocket:", e)


    def send_to_websocket(self, payload: dict):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                self.ws.send(FERNET_KEY.encrypt(json.dumps(payload, ensure_ascii=False).encode()))
            except Exception as e:
                print("Ошибка отправки в WebSocket:", e)
        else:
            print("Нет соединения с WebSocket")

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def make_public_key(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        public_key = private_key.public_key()

        pem_private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )

        with open('private_key', 'wb') as file:
            file.write(pem_private_key)

        pem_public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return pem_public_key.decode()

    def encode_message(self, message, public_key):
        public_key = serialization.load_pem_public_key(bytes(public_key, encoding='UTF-8'))

        message = bytes(message, encoding='UTF-8')
        message = public_key.encrypt(
            message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return base64.encodebytes(message).decode('ascii')

    def get_private_key(self):
        with open('private_key', 'rb') as file:
            data = file.read()

        private_key = serialization.load_pem_private_key(data, None)

        return private_key

    def register(self, nickname, email, password):
        data = {
            "action": "register",
            "nickname": nickname,
            'email': email,
            "password": self.hash_password(password)
        }
        self.send_to_websocket(data)

    # ------- TEST ---------

    def test_register(self):
        self.register('MaksMesh', 'maksmesh2010@gmail.com', '54321')

    def login(self):
        data = {
            "action": "login",
            'email': 'maksimmeskov557@gmail.com',
            "password": self.hash_password('54321')
        }
        self.send_to_websocket(data)

    def create_chat_with_user(self):
        data = {
            "action": "create_chat_with_user",
            'token': '1c0865fada83428d9537d1d1851d1bd9',
            "username": "MaksMesh"
        }
        self.send_to_websocket(data)

    def get_public_key(self):
        data = {
            "action": "get_public_key",
            'token': '1c0865fada83428d9537d1d1851d1bd9',
            "username": "MaksMesh"
        }
        self.send_to_websocket(data)

    def send_message(self, pub_key):
        message = 'Урааааааа!!!!!!!'

        message = self.encode_message(message, pub_key)

        data = {
            "action": "send_message",
            'token': '1c0865fada83428d9537d1d1851d1bd9',
            "to_username": "MaksMesh",
            "message": message,
            "chat_id": 1
        }

        self.send_to_websocket(data)

    def get_messages(self):
        data = {
            "action": "get_messages",
            'token': '16abb270ddfa4e19b97c465c3d761c4d',
            "chat_id": 1
        }

        self.send_to_websocket(data)

    def get_chats(self):
        data = {
            "action": "get_chats",
            'token': '82c40eb1b194459ba99b5feeb13140ef'
        }

        self.send_to_websocket(data)


Test()