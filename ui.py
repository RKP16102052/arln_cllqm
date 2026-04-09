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
from kivy.uix.image import Image
from kivymd.uix.dialog import MDDialog

from kivy.utils import platform
from kivy.clock import Clock
from plyer import filechooser
import validators

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet

from PIL import Image as PILImage
import threading
import hashlib
import websocket
import json
import os
import base64
import io

HOST = '127.0.0.1'  # Был "130.12.45.26"
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
CHATS_DIR = os.path.join(ARLENE_DIR, 'chats')
os.makedirs(CHATS_DIR, exist_ok=True)

TOKEN_FILE = os.path.join(ARLENE_DIR, 'token')
NICKNAME_FILE = os.path.join(ARLENE_DIR, 'nickname.txt')
CHATS_FILE = os.path.join(ARLENE_DIR, 'chats.json')


class ChatItem(MDBoxLayout, MDFlatButton):
    def __init__(self, name, chat_id, image, chat_screen, **kwargs):
        super().__init__(orientation="horizontal", size_hint=(4, None), **kwargs)
        self.chat_id = chat_id
        self.chat_screen = chat_screen

        self.halign = 'left'
        self.height = 70

        self.line_color = 'gray'
        self.line_width = 2

        image_container = MDBoxLayout()
        image_container.padding = (-100, 0, 0, 5)

        self.image = Image(source=image, size_hint=(None, None))
        self.image.size = (50, 50)
        self.image.allow_stretch = True
        self.image.keep_ratio = False
        self.image.center_x = -100
        image_container.add_widget(self.image)

        text_container = MDBoxLayout()
        self.label = MDLabel(text=name, halign="left", valign="middle", size_hint=(1, None))
        text_container.padding = (-110, 0, 0, -20)
        text_container.add_widget(self.label)

        self.on_release = lambda *args: self.on_open()

        self.add_widget(image_container)
        self.add_widget(text_container)

    def on_open(self):
        self.chat_screen.open_chat(self.chat_id)

    def reload(self):
        self.image.reload()


class MessageItem(MDBoxLayout):
    def __init__(self, name, text, own_message=True, content_type="text", **kwargs):
        super().__init__(orientation="horizontal", spacing=10, padding=(10, 0, 10, 0), size_hint_y=None,
                         **kwargs)

        self.root = MDBoxLayout(orientation="vertical")
        space_container = MDBoxLayout()

        if own_message:
            self.root.md_bg_color = '#751fff'
        else:
            self.root.md_bg_color = '#af0fff'

        self.root.size_hint_x = 0.975
        self.root.radius = 10

        self.name_label = MDLabel(text=name, valign="middle", padding=(10, 20, 10, 0))
        self.name_label.font_size = 19
        self.name_label.bind(texture_size=self.name_label.setter("size"))
        self.root.add_widget(self.name_label)

        self.text_label = MDLabel(text=text, valign="top", padding=(15, 0, 15, 0))
        self.text_label.bind(texture_size=self.text_label.setter("size"))
        self.root.add_widget(self.text_label)

        if own_message:
            self.name_label.halign = 'left'
            self.text_label.halign = 'left'
        else:
            self.name_label.halign = 'right'
            self.text_label.halign = 'right'

        self.add_widget(self.root)

        self.add_widget(space_container, not own_message)

        Clock.schedule_once(lambda dt: self.adjust_size())

    def adjust_size(self):
        self.height = self.name_label.texture_size[1] + self.text_label.texture_size[1] + 25
        self.name_label.size_hint_y = self.name_label.texture_size[1] / self.height


class AuthTab(MDBoxLayout, MDTabsBase):
    pass


class AuthScreen(MDScreen):
    current_tab = 'Авторизация'

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

        self.login_email = MDTextField(hint_text="Электронная почта")
        self.login_password = MDTextField(hint_text="Пароль", password=True)

        error_box_login = MDBoxLayout(
            orientation="vertical",
            spacing=10,
            padding=(0, 20),
            adaptive_height=True,
            size_hint_y=None
        )

        self.login_error = MDLabel(text='')
        error_box_login.add_widget(self.login_error)

        login_box.add_widget(self.login_email)
        login_box.add_widget(self.login_password)
        login_box.add_widget(error_box_login)

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
        self.reg_login_btn = MDRaisedButton(text="Войти", on_release=lambda *_: self.login_or_reg(), font_size=20)
        button_box.add_widget(self.reg_login_btn)
        root.add_widget(button_box)

        self.add_widget(root)

    def show_error(self, message, reg: bool):
        if reg:
            if message:
                self.reg_error.text = 'Ошибка: ' + message
            else:
                self.reg_error.text = ''
        else:
            if message:
                self.login_error.text = 'Ошибка: ' + message
            else:
                self.login_error.text = ''

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
        else:
            email = self.login_email.text
            password = self.login_password.text
            self.show_error('', False)

            if not email or not password:
                self.show_error('Заполните все поля.', False)
            else:
                if not validators.email(email):
                    self.show_error('Неправильный формат почты.', False)
                else:
                    if len(password) < 8:
                        self.show_error('Пароль должен содержать от 8 символов.', False)
                    else:
                        data = {
                            "action": "login",
                            'email': email,
                            "password": self.hash_password(password)
                        }
                        if not self.send_to_websocket(data):
                            self.show_error('Нет соединения с WebSocket.', False)

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

        hint_text = MDLabel(
            text='На указанную почту отправлен код подтверждения. \nЕсли код не приходит в течение 1 минуты, попробуйте нажать "назад"\nи зарегистрироваться заново.')
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
    current_chat_id = None
    messages_query = []

    def on_pre_enter(self):
        self.clear_widgets()

        root = MDBoxLayout(orientation="vertical", padding=20, spacing=10)

        split_box = MDBoxLayout(orientation="horizontal")

        chats_side = MDBoxLayout(orientation="vertical")
        chats_side.size_hint_x = 0.52

        chats_scroll = MDScrollView(do_scroll_x=False)
        chats_scroll.always_overscroll = False
        self.chats_box = MDBoxLayout(orientation="vertical", spacing=0, adaptive_size=True)

        chats_scroll.add_widget(self.chats_box)

        buttons_container = MDBoxLayout(orientation="horizontal", spacing=10)
        buttons_container.size_hint_y = 0.15

        button_space_container = MDBoxLayout()

        settings_chat_button = MDIconButton(icon='account-settings')
        settings_chat_button.md_bg_color = '#751fff'
        settings_chat_button.on_press = self.go_to_settings

        add_chat_button = MDIconButton(icon='plus')
        add_chat_button.md_bg_color = '#751fff'
        add_chat_button.on_press = self.go_to_add_chat

        buttons_container.add_widget(button_space_container)
        buttons_container.add_widget(settings_chat_button)
        buttons_container.add_widget(add_chat_button)

        chats_side.add_widget(chats_scroll)
        chats_side.add_widget(buttons_container)

        chats_messages_box = MDBoxLayout(orientation="vertical", padding=20, spacing=30)

        self.chat_content_scroll = MDScrollView(do_scroll_x=False)
        self.chat_content = MDBoxLayout(orientation="vertical", spacing=30)
        self.chat_content_scroll.size_hint_y = 5
        self.chat_content.size_hint_y = None
        self.chat_content.bind(minimum_height=self.chat_content.setter("height"))

        self.chat_content_scroll.add_widget(self.chat_content)

        message_text_box = MDBoxLayout(orientation="horizontal", spacing=20)

        self.message_text = MDTextField(multiline=True, font_size=20)
        send_button = MDIconButton(icon='send')
        send_button.on_release = self.send_message

        message_text_box.add_widget(self.message_text)
        message_text_box.add_widget(send_button)

        chats_messages_box.add_widget(self.chat_content_scroll)
        chats_messages_box.add_widget(message_text_box)

        split_box.add_widget(chats_side)
        split_box.add_widget(chats_messages_box)

        root.add_widget(split_box)
        self.add_widget(root)

        self.update_chats()

    def set_app(self, app):
        self.app = app

    def go_to_add_chat(self):
        self.app.sm.current = 'add_chat'

    def update_chats(self):
        with open(CHATS_FILE) as file:
            data = json.load(file)

        self.chats_box.clear_widgets()

        for i in data:
            self.chats_box.add_widget(ChatItem(i['name'], i['id'], '', self))

    def open_chat(self, chat_id, download: bool = True):
        try:
            self.current_chat_id = chat_id

            if download:
                self.chat_content_scroll.scroll_y = 0
                self.download_chat(chat_id)

            with open(os.path.join(CHATS_DIR, str(chat_id))) as file:
                data = json.load(file)

            Clock.schedule_once(lambda dt: self.show_messages(data))
        except Exception:
            self.show_messages([])

    def show_messages(self, data):
        self.chat_content.clear_widgets()

        for i in data:
            own_message = self.app.nickname == i['from']
            self.chat_content.add_widget(MessageItem(i['from'], i['message'], own_message))

    def download_chat(self, chat_id):
        chat_file = os.path.join(CHATS_DIR, str(chat_id))

        last_time = None

        if os.path.exists(chat_file):
            with open(chat_file) as file:
                data = json.load(file)

            if data:
                last_time = data[-1]['time']

        data = {
            "action": "get_messages",
            'token': self.app.token,
            "chat_id": chat_id
        }

        if last_time is not None:
            data['time'] = last_time

        self.app.send_to_websocket(data)

    def send_message(self):
        message = self.message_text.text

        if self.current_chat_id is not None:
            self.messages_query.append({self.current_chat_id: message})

            data = {
                "action": "get_members_keys",
                'token': self.app.token,
                "chat_id": self.current_chat_id
            }

            self.app.send_to_websocket(data)
            self.message_text.text = ''

    def get_current_chat_messages(self):
        if self.current_chat_id is not None:
            self.download_chat(self.current_chat_id)

    def go_to_settings(self):
        # filechooser.open_file()
        self.app.open_settings()


class AddChatScreen(MDScreen):
    def on_pre_enter(self):
        self.clear_widgets()

        if self.app.private_key is None:
            self.app.load_private_key()

        root = MDBoxLayout(orientation='vertical', padding=10, spacing=20)

        header_box = MDBoxLayout(orientation='horizontal')

        back_button = MDIconButton(icon='arrow-left', md_bg_color='#751fff')
        back_button.on_release = self.back
        header_space_container = MDBoxLayout()
        header_space_container.size_hint_x = 0.5
        header_label = MDLabel(text='Добавить чат')
        header_label.font_size = 30

        header_box.add_widget(back_button)
        header_box.add_widget(header_space_container)
        header_box.add_widget(header_label)

        content_box = MDBoxLayout()
        content_box.size_hint_y = 10

        tabs = MDTabs()

        personal_tab = AuthTab(title='Личный чат')

        personal_layout = MDBoxLayout(orientation='vertical', padding=10, spacing=20)

        self.person_text_personal = MDTextField(hint_text='Имя пользователя')
        self.error_text_personal = MDLabel(text='')
        add_button_personal = MDIconButton(icon='plus', md_bg_color='#751fff')
        add_button_personal.on_release = self.add_chat_personal
        space_personal = MDBoxLayout(size_hint_y=10)

        personal_layout.add_widget(self.person_text_personal)
        personal_layout.add_widget(self.error_text_personal)
        personal_layout.add_widget(add_button_personal)
        personal_layout.add_widget(space_personal)

        personal_tab.add_widget(personal_layout)

        group_tab = AuthTab(title='Группа')

        group_layout = MDBoxLayout(orientation='vertical', padding=10, spacing=20)

        self.group_name = MDTextField(hint_text='Название группы')

        self.members_text = MDTextField(hint_text='Участники группы через ", ", например: "1, 2, 3"')

        self.error_text_group = MDLabel(text='')
        add_button_group = MDIconButton(icon='plus', md_bg_color='#751fff')
        add_button_group.on_release = self.add_group
        space_group = MDBoxLayout(size_hint_y=10)

        group_layout.add_widget(self.group_name)
        group_layout.add_widget(self.members_text)
        group_layout.add_widget(self.error_text_group)
        group_layout.add_widget(add_button_group)
        group_layout.add_widget(space_group)

        group_tab.add_widget(group_layout)

        tabs.add_widget(personal_tab)
        tabs.add_widget(group_tab)

        content_box.add_widget(tabs)

        root.add_widget(header_box)
        root.add_widget(content_box)

        self.add_widget(root)

    def set_app(self, app):
        self.app = app

    def back(self):
        self.app.open_chat()

    def show_error(self, message, personal: bool):
        if personal:
            if message:
                self.error_text_personal.text = 'Ошибка: ' + message
            else:
                self.error_text_personal.text = ''
        else:
            if message:
                self.error_text_group.text = 'Ошибка: ' + message
            else:
                self.error_text_group.text = ''

    def add_chat_personal(self):
        name = self.person_text_personal.text
        self.show_error('', True)

        if not name:
            self.show_error('Неверное имя пользователя.', True)

        data = {
            "action": "create_chat_with_user",
            'token': self.app.token,
            "username": name
        }
        self.app.send_to_websocket(data)

    def add_group(self):
        name = self.group_name.text
        self.show_error('', False)

        if not name:
            self.show_error('Неверное название группы.', False)

        usernames = self.members_text.text.split(', ')

        if not usernames:
            self.show_error('Неверный формат участников.', False)

        data = {
            "action": "create_group",
            'token': self.app.token,
            "name": name,
            "usernames": usernames
        }
        self.app.send_to_websocket(data)


class SettingsScreen(MDScreen):
    def on_pre_enter(self):
        self.clear_widgets()

        root = MDBoxLayout(orientation='vertical', padding=10, spacing=20)

        header_box = MDBoxLayout(orientation='horizontal')

        back_button = MDIconButton(icon='arrow-left', md_bg_color='#751fff')
        back_button.on_release = self.back
        header_space_container = MDBoxLayout()
        header_space_container.size_hint_x = 0.6
        header_label = MDLabel(text='Настройки')
        header_label.font_size = 30

        header_box.add_widget(back_button)
        header_box.add_widget(header_space_container)
        header_box.add_widget(header_label)

        content_box = MDBoxLayout(orientation='vertical', size_hint_y=8)

        image_container = MDBoxLayout(size_hint=(1, 7))

        h_image_container = MDBoxLayout(orientation='horizontal')

        self.image = Image(source='image', size_hint=(1, 1))
        self.image.allow_stretch = True
        self.image.keep_ratio = False

        h_image_container.add_widget(MDBoxLayout(size_hint_x=1))
        h_image_container.add_widget(self.image)
        h_image_container.add_widget(MDBoxLayout(size_hint_x=1))

        image_container.add_widget(h_image_container)

        h_upload_box = MDBoxLayout(orientation='horizontal')

        upload_image_button = MDIconButton(icon='upload', md_bg_color='#751fff')
        upload_image_button.on_press = self.upload_avatar

        h_upload_box.add_widget(MDBoxLayout(size_hint_x=1))
        h_upload_box.add_widget(upload_image_button)
        h_upload_box.add_widget(MDBoxLayout(size_hint_x=1))

        content_box.add_widget(h_upload_box)

        h_token_box = MDBoxLayout(orientation='horizontal')

        export_token_text = MDLabel(text='Экспортировать ключ')
        export_token_button = MDIconButton(icon='file-export', md_bg_color='#751fff')
        export_token_button.on_press = self.export_key_warn

        h_token_box.add_widget(MDBoxLayout(size_hint_x=1))
        h_token_box.add_widget(export_token_text)
        h_token_box.add_widget(export_token_button)
        h_token_box.add_widget(MDBoxLayout(size_hint_x=1))

        content_box.add_widget(h_token_box)
        content_box.add_widget(MDBoxLayout(size_hint_y=1))

        h_exit_box = MDBoxLayout(orientation='horizontal')

        exit_button = MDFlatButton(text='Выйти из аккаунта', text_color='#ff7a7a')
        exit_button.font_size = 18
        exit_button.theme_text_color = 'Custom'
        exit_button.on_press = self.logout_dial

        h_exit_box.add_widget(MDBoxLayout(size_hint_x=1))
        h_exit_box.add_widget(exit_button)
        h_exit_box.add_widget(MDBoxLayout(size_hint_x=1))

        content_box.add_widget(h_exit_box)
        
        h_permanent_exit_box = MDBoxLayout(orientation='horizontal')

        permanent_exit_button = MDFlatButton(text='Выйти из аккаунта с устройства', text_color='red')
        permanent_exit_button.font_size = 18
        permanent_exit_button.theme_text_color = 'Custom'
        permanent_exit_button.on_press = self.permanent_logout_dial

        h_permanent_exit_box.add_widget(MDBoxLayout(size_hint_x=1))
        h_permanent_exit_box.add_widget(permanent_exit_button)
        h_permanent_exit_box.add_widget(MDBoxLayout(size_hint_x=1))

        content_box.add_widget(h_permanent_exit_box)

        content_box.add_widget(MDBoxLayout(size_hint_y=1))

        root.add_widget(header_box)
        root.add_widget(image_container)
        root.add_widget(content_box)

        self.add_widget(root)

    def set_app(self, app):
        self.app = app

    def back(self):
        self.app.open_chat()

    def export_key_warn(self):
        self.dialog = MDDialog(
            title="Экспорт ключа",
            text="Экспорт этого файла позволит вам войти на другом устройстве. Не передавайте этот файл другим и не отправляйте его по интернету.",
            buttons=[
                MDFlatButton(text="Экспорт", on_release=lambda x: self.export_key_dial(True)),
                MDFlatButton(text="Отмена", on_release=lambda x: self.export_key_dial(False)),
            ],
        )

        self.dialog.open()

    def export_key_dial(self, export: bool):
        self.dialog.dismiss()

        if export:
            self.export_key()

    def export_key(self):
        save_file = filechooser.save_file()

        if save_file is not None:
            key_file = os.path.join(KEYS_DIR, self.app.token)
            if os.path.exists(key_file):
                with open(key_file, 'rb') as file:
                    key = file.read().decode()

                with open(save_file[0], 'w') as file:
                    file.writelines([self.app.token + '\n', key])

    def logout_dial(self):
        self.dialog = MDDialog(
            title="Выход из аккаунта",
            text="Вы уверены?",
            buttons=[
                MDFlatButton(text="Да", on_release=lambda x: self.logout()),
                MDFlatButton(text="Отмена", on_release=lambda x: self.dialog.dismiss()),
            ],
        )

        self.dialog.open()

    def permanent_logout_dial(self):
        self.per_logout_button = MDFlatButton(text="", on_release=lambda x: self.permanent_logout())
        self.per_logout_button.disabled = True

        self.dialog = MDDialog(
            title="Выход из аккаунта",
            text="ВНИМАНИЕ!!! Если вы выйдите из аккаунта таким способом, то вам придётся заново импортировать ключ. Если у вас не осталось авторизованных аккаунтов и файла ключа, то вы потеряете доступ к своему аккаунту!!!",
            buttons=[
                self.per_logout_button,
                MDFlatButton(text="Отмена", on_release=lambda x: self.dialog.dismiss()),
            ],
        )

        self.dialog.open()

        Clock.schedule_once(lambda dt: self.activate_dial_button(), 5)

    def logout(self):
        self.dialog.dismiss()
        self.app.logout()

    def permanent_logout(self):
        self.dialog.dismiss()

        try:
            os.remove(os.path.join(KEYS_DIR, self.app.token))
        except Exception:
            pass

        self.app.logout()

    def activate_dial_button(self):
        self.per_logout_button.text = 'Выйти'
        self.per_logout_button.disabled = False

    def upload_avatar(self):
        image = filechooser.open_file()

        try:
            if image is not None:
                image = PILImage.open(image[0]).resize((256, 256))

            byte_buff = io.BytesIO()

            image.save(byte_buff, format='PNG')

            image = base64.encodebytes(byte_buff.getvalue()).decode('ascii')

            data = {
                "action": "upload_avatar",
                'token': self.app.token,
                "image": image
            }

            self.app.send_to_websocket(data)
        except Exception:
            pass


class ImportKeyScreen(MDScreen):
    def on_pre_enter(self):
        self.clear_widgets()

        root = MDBoxLayout(orientation='vertical', padding=10, spacing=20)

        header_box = MDBoxLayout(orientation='horizontal')

        back_button = MDIconButton(icon='arrow-left', md_bg_color='#751fff')
        back_button.on_release = self.back
        header_space_container = MDBoxLayout()
        header_space_container.size_hint_x = 0.5
        header_label = MDLabel(text='Импорт ключа')
        header_label.font_size = 30

        header_box.add_widget(back_button)
        header_box.add_widget(header_space_container)
        header_box.add_widget(header_label)

        content_box = MDBoxLayout(size_hint_y=10, orientation='vertical')

        hint_label_box = MDBoxLayout(orientation='horizontal')

        hint_label = MDLabel(text='Для правильный работы приложения требуется импортировать файл ключа. Чтобы получить его, перейдите в приложение на авторизованном в этот аккаунт устройстве, зайдите в настройки и нажмите "Экспорт ключа".')
        hint_label.font_size = 20

        hint_label_box.add_widget(MDBoxLayout(size_hint_x=0.2))
        hint_label_box.add_widget(hint_label)
        hint_label_box.add_widget(MDBoxLayout(size_hint_x=0.2))

        content_box.add_widget(hint_label_box)

        import_box = MDBoxLayout(orientation='horizontal', size_hint_y=0.2)

        import_label = MDLabel(text='Импортировать ключ')
        import_label.font_size = 20

        import_button = MDIconButton(icon='import', md_bg_color='#751fff')
        import_button.on_press = self.import_key

        import_box.add_widget(MDBoxLayout(size_hint_x=0.5))
        import_box.add_widget(import_label)
        import_box.add_widget(import_button)
        import_box.add_widget(MDBoxLayout(size_hint_x=1.8))

        content_box.add_widget(import_box)

        error_box = MDBoxLayout(orientation='horizontal')

        self.error_label = MDLabel()
        self.error_label.font_size = 20

        error_box.add_widget(MDBoxLayout(size_hint_x=0.2))
        error_box.add_widget(self.error_label)
        error_box.add_widget(MDBoxLayout(size_hint_x=0.2))

        content_box.add_widget(error_box)
        content_box.add_widget(MDBoxLayout(size_hint_y=1))

        root.add_widget(header_box)
        root.add_widget(content_box)

        self.add_widget(root)

    def set_app(self, app):
        self.app = app

    def back(self):
        self.app.logout()

    def import_key(self):
        key_file = filechooser.open_file()
        self.show_error('')

        try:
            if key_file is not None:
                with open(key_file[0]) as file:
                    data = file.readlines()

                token, key = data[0].rstrip('\n'), ''.join(data[1:])

                if token != self.app.token:
                    self.show_error('Неверный файл.')
                else:
                    with open(os.path.join(KEYS_DIR, token), 'wb') as file:
                        file.write(bytes(key, encoding='UTF-8'))

                    self.app.auto_login()
        except Exception:
            self.show_error('Не удалось прочитать файл.')

    def show_error(self, text):
        if text:
            self.error_label.text = 'Ошибка: ' + text
        else:
            self.error_label.text = ''


class ScreenManager(MDScreenManager):
    pass


class ChatApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Purple"
        self.theme_cls.primary_hue = '800'

        self.nickname = None
        self.token = None
        self.private_key = None
        self.get_chats_event = None
        self.get_current_messages_event = None

        self.sm = ScreenManager()
        self.auth_screen = AuthScreen(name="auth")
        self.auth_screen.set_app(self)
        self.code_screen = CodeScreen(name="code")
        self.code_screen.set_app(self)
        self.import_key_screen = ImportKeyScreen(name="import_key")
        self.import_key_screen.set_app(self)

        self.chat_screen = ChatScreen(name="chat")
        self.chat_screen.set_app(self)
        self.add_chat_screen = AddChatScreen(name='add_chat')
        self.add_chat_screen.set_app(self)
        self.settings_screen = SettingsScreen(name='settings')
        self.settings_screen.set_app(self)

        self.sm.add_widget(self.auth_screen)
        self.sm.add_widget(self.code_screen)
        self.sm.add_widget(self.chat_screen)
        self.sm.add_widget(self.add_chat_screen)
        self.sm.add_widget(self.settings_screen)
        self.sm.add_widget(self.import_key_screen)

        self.start_websocket()

        Clock.schedule_once(lambda dt: self.auto_login(), 2)

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
            elif action == 'login':
                if data['status'] == 'OK' and self.token is None:
                    self.token = data['token']

                    with open(TOKEN_FILE, 'w') as file:
                        file.write(self.token)

                    if os.path.exists(os.path.join(KEYS_DIR, self.token)):
                        self.auto_login()
                    else:
                        Clock.schedule_once(lambda dt: self.go_to_import_key_screen())
                elif data['status'] == 'OK':
                    if os.path.exists(os.path.join(KEYS_DIR, self.token)):
                        self.auto_login()
                else:
                    self.auth_screen.show_error(data['message'], False)
            elif action == 'get_chats' and data['status'] == 'OK':
                with open(CHATS_FILE, 'w') as file:
                    json.dump(data['chats'], file)

                Clock.schedule_once(lambda dt: self.update_chats())
            elif action == 'create_chat_with_user':
                if data['status'] == 'OK':
                    Clock.schedule_once(lambda dt: self.open_chat())
                else:
                    self.add_chat_screen.show_error(data['message'], True)
            elif action == 'get_messages':
                if data['status'] == 'OK':
                    fin_data = []
                    padd = padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )

                    for i in data['data']:
                        message = base64.decodebytes(i['message'].encode('ascii'))
                        fin = bytes()

                        for j in range(0, len(message), 256):
                            print(self.private_key.decrypt(message[j:j + 256], padd), j)
                            fin += self.private_key.decrypt(message[j:j + 256], padd)

                        fin = fin.decode()

                        fin_data.append({'from': i['from'], 'message': fin,
                                         'time': i['time']})

                    chat_file = os.path.join(CHATS_DIR, str(data['chat_id']))

                    if os.path.exists(chat_file):
                        with open(chat_file) as file:
                            f_data = json.load(file)

                        fin_data = f_data + fin_data

                    with open(chat_file, 'w') as file:
                        json.dump(fin_data, file)

                    if self.chat_screen.current_chat_id == data['chat_id']:
                        Clock.schedule_once(
                            lambda dt: self.chat_screen.open_chat(self.chat_screen.current_chat_id, False))
            elif action == 'get_members_keys':
                if data['status'] == 'OK':
                    chat_id = data['chat_id']
                    messages = [list(i.values())[0] for i in
                                list(filter(lambda x: chat_id in list(x.keys()), self.chat_screen.messages_query))]

                    for i in data['content']:
                        public_key = serialization.load_pem_public_key(bytes(list(i.values())[0], encoding='UTF-8'))

                        for or_message in messages:
                            or_message = bytes(or_message, encoding='UTF-8')
                            
                            fin = bytes()

                            for j in range(0, len(or_message), 180):
                                message = public_key.encrypt(
                                    or_message[j:j + 180],
                                    padding.OAEP(
                                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                        algorithm=hashes.SHA256(),
                                        label=None
                                    )
                                )

                                fin += message

                            fin = base64.encodebytes(fin).decode('ascii')

                            data = {
                                "action": "send_message",
                                'token': self.token,
                                "to_username": list(i.keys())[0],
                                "message": fin,
                                "chat_id": chat_id
                            }

                            self.send_to_websocket(data)


                    for i in list(filter(lambda x: chat_id in list(x.keys()), self.chat_screen.messages_query)):
                        del self.chat_screen.messages_query[self.chat_screen.messages_query.index(i)]
            elif action == 'create_group':
                if data['status'] == 'OK':
                    Clock.schedule_once(lambda dt: self.open_chat())
                else:
                    self.add_chat_screen.show_error(data['message'], False)

        def on_error(ws, error):
            print("WebSocket ошибка:", error)

        def on_close(ws, *args):
            print("WebSocket закрыт", *args)
            Clock.schedule_once(lambda dt: self.start_websocket(), 3)

        try:
            self.ws = websocket.WebSocketApp(
                WEBSOCKET_URL,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )

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
        self.get_chats()

        if self.get_chats_event is None:
            self.get_chats_event = Clock.schedule_interval(lambda dt: self.get_chats(), 5)

        if self.get_current_messages_event is None:
            self.get_chats_event = Clock.schedule_interval(lambda dt: self.chat_screen.get_current_chat_messages(), 5)

        self.sm.current = 'chat'

    def auto_login(self):
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE) as file:
                self.token = file.read()

            if not os.path.exists(os.path.join(KEYS_DIR, self.token)):
                self.go_to_import_key_screen()
            else:
                data = {
                    "action": "get_name",
                    "token": self.token
                }

                self.load_private_key()

                self.send_to_websocket(data)

    def get_chats(self):
        data = {
            "action": "get_chats",
            'token': self.token
        }

        self.send_to_websocket(data)

    def update_chats(self):
        self.chat_screen.update_chats()

    def load_private_key(self):
        with open(os.path.join(KEYS_DIR, self.token), 'rb') as file:
            data = file.read()

        self.private_key = serialization.load_pem_private_key(data, None)

    def open_settings(self):
        self.sm.current = 'settings'

    def go_to_import_key_screen(self):
        self.sm.current = 'import_key'

    def logout(self):
        self.nickname = None
        self.token = None
        self.private_key = None

        if self.get_chats_event is not None:
            self.get_chats_event.cancel()
            self.get_chats_event = None

        if self.get_current_messages_event is not None:
            self.get_current_messages_event.cancel()
            self.get_current_messages_event = None

        try:
            os.remove(TOKEN_FILE)
        except FileNotFoundError:
            pass

        try:
            os.remove(NICKNAME_FILE)
        except FileNotFoundError:
            pass
        
        try:
            os.remove(CHATS_FILE)
        except FileNotFoundError:
            pass

        self.sm.current = 'auth'

    def start_websocket(self):
        self.ws = None
        self.ws_thread = threading.Thread(target=self.connect_websocket, daemon=True)
        self.ws_thread.start()


if __name__ == '__main__':
    ChatApp().run()