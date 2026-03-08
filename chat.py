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

from plyer import filechooser

import os
import shutil
import time
import threading
import websocket
import base64
import json

if platform == "android":
    DOWNLOAD_DIR = "/storage/emulated/0/Downloads/Arlene Colloquium"
else:
    DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
WEBSOCKET_URL = "ws://130.12.45.26:8765"  # поменяй на адрес твоего сервера
HISTORY_FILE = os.path.join(DOWNLOAD_DIR, "chat_history.json")
TOKEN_FILE = os.path.join(DOWNLOAD_DIR, "token.txt")


class ChatItem(MDBoxLayout):
    def __init__(self, text, delete_callback=None, download_callback=None, item_type="text", **kwargs):
        super().__init__(orientation="horizontal", spacing=10, padding=(10, 0, 10, 0), size_hint_y=None, height=48,
                         **kwargs)
        self.label = MDLabel(text=text, halign="left", valign="middle")
        self.label.bind(texture_size=self.label.setter("size"))
        self.add_widget(self.label)
        if item_type == "file" and download_callback:
            download_icon = MDIconButton(icon="download")
            download_icon.on_release = lambda: download_callback()
            self.add_widget(download_icon)
        delete_icon = MDIconButton(icon="delete")
        delete_icon.on_release = lambda: delete_callback(self) if delete_callback else None
        self.add_widget(delete_icon)


class AuthTab(MDBoxLayout, MDTabsBase):
    pass


class AuthScreen(MDScreen):
    mode = StringProperty("login")  # "login" or "register"

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

        self.reg_nick = MDTextField(hint_text="Имя")
        self.reg_phone = MDTextField(hint_text="Номер телефона", input_filter="int")
        self.reg_password = MDTextField(hint_text="Пароль", password=True)

        sms_box = MDBoxLayout(orientation="horizontal", spacing=10, size_hint_y=None, height="48dp")
        self.reg_sms = MDTextField(hint_text="Код из СМС", size_hint_x=0.7)
        send_sms_btn = MDRaisedButton(
            text="Отправить код",
            size_hint_x=0.3,
            on_release=lambda *_: self.send_sms_code(to="register")
        )
        sms_box.add_widget(self.reg_sms)
        sms_box.add_widget(send_sms_btn)

        reg_box.add_widget(self.reg_nick)
        reg_box.add_widget(self.reg_phone)
        reg_box.add_widget(self.reg_password)
        reg_box.add_widget(sms_box)

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
        login_btn = MDRaisedButton(text="Войти", on_release=lambda *_: self.login())
        reg_btn = MDRaisedButton(text="Зарегистрироваться", on_release=lambda *_: self.register())
        button_box.add_widget(login_btn)
        button_box.add_widget(reg_btn)
        root.add_widget(button_box)

        # Подпись/информация
        self.info_label = MDLabel(text="", halign="center", size_hint_y=None, height="40dp")
        root.add_widget(self.info_label)

        self.add_widget(root)

    def send_sms_code(self, to="register"):
        if to == "login":
            phone = (self.login_phone.text or "").strip()
        else:
            phone = (self.reg_phone.text or "").strip()

        if not phone:
            self.info_label.text = "Введите номер телефона"
            return

        # Пока просто заглушка
        self.info_label.text = f"""Код отправлен на {phone} (Пока СМС сервер не подключен. для продолжения
        используйте код: 000000)"""

    def set_app(self, app):
        self.app = app

    def ws_send(self, payload: dict):
        if self.app.ws and self.app.ws.sock and self.app.ws.sock.connected:
            try:
                self.app.ws.send(json.dumps(payload, ensure_ascii=False))
            except Exception as e:
                self.info_label.text = f"Ошибка отправки: {e}"
        else:
            self.info_label.text = "Нет соединения с сервером"

    def login(self):
        phone = (self.login_phone.text or "").strip()
        password = (self.login_password.text or "").strip()
        if not phone or not password:
            self.info_label.text = "Введите телефон и пароль"
            return
        self.ws_send({"action": "login", "phone": phone, "password": password})

    def register(self):
        nick = (self.reg_nick.text or "").strip()
        phone = (self.reg_phone.text or "").strip()
        password = (self.reg_password.text or "").strip()
        sms = (self.reg_sms.text or "").strip()
        if not (nick and phone and password and sms):
            self.info_label.text = "Заполните все поля"
            return
        self.ws_send({
            "action": "register",
            "nickname": nick,
            "phone": phone,
            "password": password,
            "sms_code": sms,
        })

    # обработка ответов сервера
    def handle_auth_response(self, data: dict):
        if data.get("status") == "ok":
            token = data.get("token")
            nick = data.get("nickname")
            if token:
                try:
                    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                        f.write(token)
                except Exception:
                    pass
            self.app.set_current_user(nick, token)
            self.app.open_chat()
        else:
            self.info_label.text = data.get("message", "Ошибка аутентификации")


class ChatScreen(MDScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        root = MDBoxLayout(orientation="vertical")

        header = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=56, padding=(10, 10), spacing=10)
        self.title_label = MDLabel(text=f"Вы вошли как: {self.app.nickname}", halign="left")
        logout_btn = MDFlatButton(text="Выйти", on_release=lambda *_: self.app.logout())
        header.add_widget(self.title_label)
        header.add_widget(logout_btn)
        root.add_widget(header)

        self.chat_list = MDBoxLayout(orientation="vertical", size_hint_y=None, padding=10, spacing=5)
        self.chat_list.bind(minimum_height=self.chat_list.setter("height"))

        self.scroll = MDScrollView(size_hint=(1, 0.7))
        self.scroll.add_widget(self.chat_list)
        root.add_widget(self.scroll)

        attach_buttons = MDBoxLayout(size_hint=(1, 0.1), padding=10, spacing=10)
        file_btn = MDIconButton(icon="file", on_release=self.send_file)
        attach_buttons.add_widget(file_btn)
        root.add_widget(attach_buttons)

        input_layout = MDBoxLayout(size_hint=(1, 0.15), padding=10, spacing=10)
        self.message_input = MDTextField(hint_text="Сообщение", size_hint_x=0.75)
        send_button = MDRaisedButton(text="Отправить", size_hint_x=0.25, on_release=self.send_message)
        input_layout.add_widget(self.message_input)
        input_layout.add_widget(send_button)
        root.add_widget(input_layout)

        self.add_widget(root)

    def set_app(self, app):
        self.app = app

    def add_message(self, text):
        item = ChatItem(text=text, delete_callback=self.delete_message)
        self.chat_list.add_widget(item)
        Clock.schedule_once(lambda dt: setattr(self.scroll, 'scroll_y', 0))

    def add_file_message(self, filename, author=None, file_id=None):
        author = author or self.app.nickname
        item = ChatItem(
            text=f"{author}: {filename}",
            delete_callback=self.delete_message,
            download_callback=lambda: self.download_file_from_history(file_id) if file_id else None,
            item_type="file"
        )
        self.chat_list.add_widget(item)
        Clock.schedule_once(lambda dt: setattr(self.scroll, 'scroll_y', 0))

    def download_file_from_history(self, file_id):
        """Отправляет запрос на сервер для получения файла по file_id"""
        if not file_id:
            return
        self.app.send_to_websocket({
            "action": "download",
            "file_id": file_id
        })

    def load_history(self, messages):
        def _load(dt):
            for msg in messages:
                if msg.get("type") == "chat":
                    sender = msg.get("from", "?")
                    text = msg.get("text", "")
                    self.add_message(f"{sender}: {text}")
                elif msg.get("type") == "file":
                    sender = msg.get("from", "?")
                    filename = msg.get("filename", "файл")
                    file_id = msg.get("file_id")  # теперь file_id есть в истории
                    self.add_file_message(filename, author=sender, file_id=file_id)

        Clock.schedule_once(_load)

    def send_message(self, *_):
        message = (self.message_input.text or "").strip()
        if not message:
            return
        full_text = f"{self.app.nickname}: {message}"
        self.add_message(full_text)
        self.message_input.text = ''
        self.app.send_to_websocket({
            "action": "chat",
            "from": self.app.nickname,
            "text": message,
        })

    def send_file(self, *_):
        filechooser.open_file(on_selection=self._on_file_selected)

    def _on_file_selected(self, selection):
        if not selection:
            return
        path = selection[0]
        filename = os.path.basename(path)
        try:
            with open(path, "rb") as f:
                data = f.read()
            encoded = base64.b64encode(data).decode("utf-8")
            self.add_file_message(filename, author=self.app.nickname)
            self.app.send_to_websocket({
                "action": "file",
                "from": self.app.nickname,
                "filename": filename,
                "data": encoded,
            })
        except Exception as e:
            print("Ошибка при отправке файла:", e)

    def download_file(self, text):
        try:
            _, filename = text.split(": ", 1)
        except ValueError:
            filename = text
        target_path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(target_path):
            # сделаем копию с меткой времени
            ts = time.strftime("_%Y%m%d_%H%M%S")
            base, ext = os.path.splitext(filename)
            shutil.copy(target_path, os.path.join(DOWNLOAD_DIR, f"{base}{ts}{ext}"))
        else:
            print("Файл ещё не получен на устройстве")

    def delete_message(self, widget):
        if widget in self.chat_list.children:
            self.chat_list.remove_widget(widget)


class Root(MDScreenManager):
    pass


class ChatApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "BlueGray"

        self.nickname = None
        self.token = None

        self.sm = Root()
        self.auth_screen = AuthScreen(name="auth")
        self.auth_screen.set_app(self)
        self.chat_screen = ChatScreen(name="chat")
        self.chat_screen.set_app(self)

        self.sm.add_widget(self.auth_screen)
        self.sm.add_widget(self.chat_screen)

        self.ws = None
        self.ws_thread = threading.Thread(target=self.connect_websocket, daemon=True)
        self.ws_thread.start()

        return self.sm

    # --- navigation ---
    def open_chat(self):
        self.sm.current = "chat"

    def open_auth(self):
        self.sm.current = "auth"

    def set_current_user(self, nickname, token=None):
        self.nickname = nickname
        if token:
            self.token = token
        # обновим заголовок чата, если уже создан
        if hasattr(self.chat_screen, "title_label"):
            self.chat_screen.title_label.text = f"Вы вошли как: {self.nickname}"

    def logout(self):
        self.nickname = None
        self.token = None
        try:
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
        except Exception:
            pass
        self.open_auth()

    # --- websocket ---
    def connect_websocket(self):
        def on_message(ws, message):
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                # Поступил простой текст — отобразим как есть
                Clock.schedule_once(lambda dt: self.chat_screen.add_message(str(message)))
                return

            # Обработка истории сообщений
            if data.get("type") == "history":
                messages = data.get("messages", [])
                Clock.schedule_once(lambda dt: self.chat_screen.load_history(messages))
                return

            # ответы на аутентификацию
            if data.get("status") in ("ok", "error") and ("nickname" in data or "message" in data):
                Clock.schedule_once(lambda dt: self.auth_screen.handle_auth_response(data))
                return

            # события чата
            if data.get("type") == "chat":
                sender = data.get("from", "?")
                txt = data.get("text", "")
                Clock.schedule_once(lambda dt: self.chat_screen.add_message(f"{sender}: {txt}"))
                return

            if data.get("type") == "file":
                filename = data.get("filename")
                file_data = data.get("data")
                try:
                    if filename and file_data:
                        with open(os.path.join(DOWNLOAD_DIR, filename), "wb") as f:
                            f.write(base64.b64decode(file_data))
                        Clock.schedule_once(
                            lambda dt: self.chat_screen.add_file_message(filename, author=data.get("from", "?")))
                except Exception as e:
                    print("Ошибка сохранения файла:", e)
                return

            if data.get("type") == "file_download":
                filename = data.get("filename")
                file_data = data.get("data")
                try:
                    if filename and file_data:
                        # Сохраняем файл в папку загрузок
                        target_path = os.path.join(DOWNLOAD_DIR, filename)
                        with open(target_path, "wb") as f:
                            f.write(base64.b64decode(file_data))
                        # Можно показать уведомление, что файл сохранён
                        print(f"Файл {filename} сохранён в {DOWNLOAD_DIR}")
                except Exception as e:
                    print("Ошибка сохранения файла:", e)
                return

        def on_error(ws, error):
            print("WebSocket ошибка:", error)

        def on_close(ws, *args):
            print("WebSocket закрыт", *args)

        def on_open(ws):
            print("WebSocket соединение открыто")
            # авто-аутентификация по токену, если сохранён
            token = None
            try:
                if os.path.exists(TOKEN_FILE):
                    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                        token = f.read().strip()
            except Exception:
                pass
            if token:
                self.token = token
                self.ws.send(json.dumps({"action": "token_auth", "token": token}, ensure_ascii=False))
                # Ответ обработается в on_message -> handle_auth_response
            else:
                # показать экран логина
                Clock.schedule_once(lambda dt: self.open_auth())

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
                self.ws.send(json.dumps(payload, ensure_ascii=False))
            except Exception as e:
                print("Ошибка отправки в WebSocket:", e)
        else:
            print("Нет соединения с WebSocket")


if __name__ == '__main__':
    ChatApp().run()
