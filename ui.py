from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton, MDRaisedButton, MDFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.tab import MDTabsBase
from kivymd.uix.tab import MDTabs

from kivy.utils import platform
from kivy.clock import Clock
from kivy.properties import StringProperty
import validators

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet

import time
import threading
import hashlib
import websocket
import json
import os


HOST = '127.0.0.1' # Был "130.12.45.26" 
PORT = 8765 
FERNET_KEY = Fernet(b'b1hj9pFchWx8sOZ1oqVN3cOxLSgvcPTPUdhbS_EM5d4=')

WEBSOCKET_URL = f"ws://{HOST}:{PORT}"

LOCAL_DIR = os.path.join(os.path.expanduser("~"), ".local")
os.makedirs(LOCAL_DIR, exist_ok=True)
SHARE_DIR = os.path.join(LOCAL_DIR, 'share')
os.makedirs(SHARE_DIR, exist_ok=True)
ARLENE_DIR = os.path.join(SHARE_DIR, 'arlene_m')
os.makedirs(ARLENE_DIR, exist_ok=True)
KEYS_DIR = os.path.join(ARLENE_DIR, 'keys')
os.makedirs(KEYS_DIR, exist_ok=True)

TOKEN_FILE = os.path.join(ARLENE_DIR, 'token')
NICKNAME_FILE = os.path.join(ARLENE_DIR, 'nickname.txt')


class AuthTab(MDBoxLayout, MDTabsBase):
    pass


class AuthScreen(MDScreen):
    current_tab = 'Авторизация'
    app: ChatApp

    def on_pre_enter(self):
        self.clear_widgets()

        root = MDBoxLayout(orientation="vertical", padding=20, spacing=10)

        # Заголовок
        header_label = MDLabel(
            text="Добро пожаловать!",
            halign="center",
            font_style="H5",
            size_hint_y=None,
            height="48dp"
        )
        root.add_widget(header_label)

        # Tabs: Авторизация / Регистрация
        tabs = MDTabs()
        tabs.on_tab_switch = self.tab_switched

        # --- Login Tab ---
        login_tab = AuthTab(title="Авторизация")
        login_scroll = MDScrollView()
        login_box = MDBoxLayout(
            orientation="vertical",
            spacing=10,
            padding=(10, 10),
            adaptive_height=True,
            size_hint_y=None
        )

        self.login_phone = MDTextField(hint_text="Номер телефона", input_filter="int")
        self.login_password = MDTextField(hint_text="Пароль", password=True)

        sms_login_box = MDBoxLayout(orientation="horizontal", spacing=10, size_hint_y=None, height="48dp")
        self.login_sms = MDTextField(hint_text="Код из СМС", size_hint_x=0.7)
        send_login_sms_btn = MDRaisedButton(
            text="Отправить код",
            size_hint_x=0.3,
            on_release=lambda *_: self.send_sms_code(to="login")
        )
        sms_login_box.add_widget(self.login_sms)
        sms_login_box.add_widget(send_login_sms_btn)

        login_box.add_widget(self.login_phone)
        login_box.add_widget(self.login_password)
        login_box.add_widget(sms_login_box)

        login_scroll.add_widget(login_box)
        login_tab.add_widget(login_scroll)

        # --- Register Tab ---
        reg_tab = AuthTab(title="Регистрация")
        reg_scroll = MDScrollView()
        reg_box = MDBoxLayout(
            orientation="vertical",
            spacing=10,
            padding=(10, 10),
            adaptive_height=True,
            size_hint_y=None
        )

        self.reg_nick = MDTextField(hint_text="Имя пользователя")
        self.reg_email = MDTextField(hint_text="Электронная почта")
        self.reg_password = MDTextField(hint_text="Пароль", password=True)

        error_box_reg = MDBoxLayout(
            orientation="vertical",
            spacing=10,
            padding=(0, 20),
            adaptive_height=True,
            size_hint_y=None
        )

        self.reg_error = MDLabel(text='')
        error_box_reg.add_widget(self.reg_error)

        reg_box.add_widget(self.reg_nick)
        reg_box.add_widget(self.reg_email)
        reg_box.add_widget(self.reg_password)
        reg_box.add_widget(error_box_reg)

        reg_scroll.add_widget(reg_box)
        reg_tab.add_widget(reg_scroll)

        # Добавляем вкладки
        tabs.add_widget(login_tab)
        tabs.add_widget(reg_tab)

        # Контейнер для вкладок (растягивается на всё оставшееся место)
        tabs_container = MDBoxLayout(orientation="vertical", size_hint_y=1)
        tabs_container.add_widget(tabs)
        root.add_widget(tabs_container)

        # Нижняя часть (кнопки)
        button_box = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="56dp", spacing=10)
        self.reg_login_btn = MDRaisedButton(text="Войти", on_release=lambda *_: self.login_or_reg(), font_size = 20)
        button_box.add_widget(self.reg_login_btn)
        root.add_widget(button_box)

        self.add_widget(root)

    def show_error(self, message, reg: bool):
        if reg:
            if message:
                self.reg_error.text = 'Ошибка: ' + message
            else:
                self.reg_error.text = ''

    def tab_switched(self, *args):
        self.current_tab = args[2]

        if self.current_tab == 'Регистрация':
            self.reg_login_btn.text = 'Зарегистрироваться'
        else:
            self.reg_login_btn.text = 'Войти'

    def login_or_reg(self):
        if self.current_tab == 'Регистрация':
            nickname = self.reg_nick.text
            email = self.reg_email.text
            password = self.reg_password.text

            if not nickname or not email or not password:
                self.show_error('Заполните все поля.', True)
            else:
                if not validators.email(email):
                    self.show_error('Неправильный формат почты.', True)
                else:
                    if len(password) < 8:
                        self.show_error('Пароль должен содержать от 8 символов.', True)
                    else:
                        self.show_error('', True)
                        data = {
                            "action": "register",
                            "nickname": nickname,
                            'email': email,
                            "password": self.hash_password(password)
                        }
                        if not self.send_to_websocket(data):
                            self.show_error('Нет соединения с WebSocket.', True)
                        else:
                            with open(NICKNAME_FILE, 'w') as file:
                                file.write(nickname)

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def set_app(self, app):
        self.app = app

    def send_to_websocket(self, payload):
        return self.app.send_to_websocket(payload)

    def got_token_reg(self, token):
        with open(TOKEN_FILE, 'w') as file:
            file.write(token)

        Clock.schedule_once(lambda dt: self.app.go_to_code())


class CodeScreen(MDScreen):
    def on_pre_enter(self):
        self.clear_widgets()

        root = MDBoxLayout(orientation="vertical", padding=20, spacing=10)

        header_label = MDLabel(
            text="Код подтверждения",
            halign="center",
            font_style="H5",
            size_hint_y=None,
            height="48dp"
        )
        back_button = MDRaisedButton(text="Назад", on_release=self.back, font_size=20)

        root.add_widget(header_label)
        root.add_widget(back_button)

        content_container = MDBoxLayout(orientation="vertical", padding=(20, 0), spacing=0)

        hint_text = MDLabel(text='На указанную почту отправлен код подтверждения. \nЕсли код не приходит в течение 1 минуты, попробуйте нажать "назад"\nи зарегистрироваться заново.')
        hint_text.font_size = 22
        hint_text.adaptive_size = True
        content_container.add_widget(hint_text)

        self.code_text = MDTextField(hint_text="Код", input_filter="int")
        self.code_text.font_size = 50
        self.code_text.max_text_length = 6
        self.code_text.halign = 'center'
        content_container.add_widget(self.code_text)

        space_container1 = MDBoxLayout(orientation="vertical", size_hint_y=2)
        space_container = MDBoxLayout(orientation="vertical", size_hint_y=2)

        self.error_label = MDLabel(text='')
        self.error_label.halign = 'center'
        self.error_label.font_size = 30

        verify_button = MDRaisedButton(text="Отправить", on_release=lambda *_: self.verify(), font_size=20)

        root.add_widget(space_container1)
        root.add_widget(content_container)
        root.add_widget(self.error_label)
        root.add_widget(space_container)
        root.add_widget(verify_button)

        self.add_widget(root)

    def set_app(self, app):
        self.app = app

    def back(self, *args):
        self.app.sm.current = 'auth'

    def show_error(self, text):
        self.error_label.text = text

    def verify(self, *args):
        self.show_error('')
        code = self.code_text.text

        if len(code) != 6:
            self.show_error('Неверный код')
        else:
            code = int(code)

            try:
                with open(TOKEN_FILE) as file:
                    token = file.read()
            except Exception:
                self.back()
            else:
                key = self.make_public_key(token)

                data = {
                    "action": "register_verification",
                    "token": token,
                    'code': code,
                    "key": key
                }

                if not self.send_to_websocket(data):
                    self.show_error('Нет соединения с WebSocket.')

    def send_to_websocket(self, payload):
        return self.app.send_to_websocket(payload)

    def make_public_key(self, token):
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

        with open(os.path.join(KEYS_DIR, token), 'wb') as file:
            file.write(pem_private_key)

        pem_public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return pem_public_key.decode()


class ChatScreen(MDScreen):
    def set_app(self, app):
        self.app = app


class ScreenManager(MDScreenManager):
    pass


class ChatApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Purple"
        self.theme_cls.primary_hue = '800'

        self.nickname = None
        self.token = None

        self.sm = ScreenManager()
        self.auth_screen = AuthScreen(name="auth")
        self.auth_screen.set_app(self)
        self.code_screen = CodeScreen(name="code")
        self.code_screen.set_app(self)

        self.chat_screen = ChatScreen(name="chat")
        self.chat_screen.set_app(self)

        self.sm.add_widget(self.auth_screen)
        self.sm.add_widget(self.code_screen)
        self.sm.add_widget(self.chat_screen)

        self.ws = None
        self.ws_thread = threading.Thread(target=self.connect_websocket, daemon=True)
        self.ws_thread.start()

        # Clock.schedule_once(lambda dt: self.auto_login())

        return self.sm

    def connect_websocket(self):
        def on_message(ws, message):
            data = json.loads(FERNET_KEY.decrypt(message).decode())
            action = data.get('action')

            if action == 'register':
                if data['status'] == 'OK' and self.token is None:
                    self.token = data['token']
                    self.auth_screen.got_token_reg(self.token)
                else:
                    error = data['message']
                    self.auth_screen.show_error(error, True)
            elif action == 'register_verification':
                if data['status'] == 'OK':
                    Clock.schedule_once(lambda dt: self.open_chat())
            elif action == 'get_name':
                if data['status'] == 'OK':
                    self.nickname = data['name']
                    
                    with open(NICKNAME_FILE, 'w') as file:
                        file.write(self.nickname)

                    Clock.schedule_once(lambda dt: self.open_chat())

        def on_error(ws, error):
            print("WebSocket ошибка:", error)

        def on_close(ws, *args):
            print("WebSocket закрыт", *args)

        def on_open(ws):
            # print("WebSocket соединение открыто")
            # # авто-аутентификация по токену, если сохранён
            # token = None
            # try:
            #     if os.path.exists(TOKEN_FILE):
            #         with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            #             token = f.read().strip()
            # except Exception:
            #     pass
            # if token:
            #     self.token = token
            #     self.ws.send(json.dumps({"action": "token_auth", "token": token}, ensure_ascii=False))
            #     # Ответ обработается в on_message -> handle_auth_response
            # else:
            #     # показать экран логина
            #     Clock.schedule_once(lambda dt: self.open_auth())
            pass

        try:
            self.ws = websocket.WebSocketApp(
                WEBSOCKET_URL,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            self.ws.on_open = on_open
            self.ws.run_forever()
        except Exception as e:
            print("Ошибка подключения WebSocket:", e)

    def send_to_websocket(self, payload: dict):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                self.ws.send(FERNET_KEY.encrypt(json.dumps(payload, ensure_ascii=False).encode()))
                return True
            except Exception as e:
                print("Ошибка отправки в WebSocket:", e)
        else:
            print("Нет соединения с WebSocket")
        
        return False

    def go_to_code(self):
        self.sm.current = 'code'
    
    def open_chat(self):
        self.sm.current = 'chat'

    def auto_login(self):
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE) as file:
                self.token = file.read()
            
            data = {
                "action": "get_name",
                "token": self.token
            }

            self.send_to_websocket(data)


if __name__ == '__main__':
    ChatApp().run()