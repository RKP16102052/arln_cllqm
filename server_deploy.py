"""
Модуль отвечает за две вещи:
  1. ping_server(host, port) - быстрая проверка, что по адресу уже кто-то
     слушает нужный порт (используется при добавлении УЖЕ существующего сервера).
  2. deploy_new_server(...) - установка и запуск серверной части Arlene
     Colloquium на чистой удалённой машине по SSH (используется при
     добавлении НОВОГО сервера с нуля).

Код сервера НЕ берётся с диска клиента - удалённая машина сама скачивает
его с официального репозитория (REPO_URL) через `git clone`. Это значит,
что для установки нового сервера клиенту не нужно иметь при себе папку
Server: достаточно доступа удалённой машины в интернет к GitHub.

Ничего из этого не трогает "глобальную" сеть - это отдельный, независимый
инстанс сервера (своя база данных, свои пользователи), поэтому каждый
установленный таким образом сервер является изолированной "подсетью"
мессенджера.
"""

import posixpath
import socket
import time

import paramiko


REPO_URL = 'https://github.com/RKP16102052/arln_cllqm.git'
REMOTE_REPO_DIR = 'arlene_repo'          # куда клонируется весь репозиторий
REMOTE_SERVER_SUBDIR = 'Server'          # рабочая папка сервера внутри репозитория
SERVICE_NAME = 'arlene-server'


def ping_server(host, port, timeout=4):
    """True, если по адресу host:port кто-то принимает TCP-соединения."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _run(ssh, command, password=None, use_sudo=False, timeout=120):
    """Выполняет команду на удалённой машине. Если use_sudo=True - оборачивает
    её в `sudo -S bash -c '...'` и подаёт пароль администратора в stdin."""

    if use_sudo:
        full_command = "sudo -S -p '' bash -c '{}'".format(command)
    else:
        full_command = command

    stdin, stdout, stderr = ssh.exec_command(full_command, timeout=timeout)

    if use_sudo and password is not None:
        stdin.write(password + '\n')
        stdin.flush()

    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors='ignore')
    err = stderr.read().decode(errors='ignore')

    return exit_code, out, err


def _patch_host_port(server_py_source, port):
    """Подменяет строки HOST/PORT в исходнике server.py так, чтобы сервер
    слушал на 0.0.0.0 (все интерфейсы) на выбранном порту."""

    new_lines = []

    for line in server_py_source.splitlines():
        stripped = line.strip()

        if stripped.startswith('HOST '):
            new_lines.append("HOST = '0.0.0.0'")
        elif stripped.startswith('PORT '):
            new_lines.append(f"PORT = {port}")
        else:
            new_lines.append(line)

    return '\n'.join(new_lines) + '\n'


def deploy_new_server(host, admin_user, admin_password, port=8765, progress_cb=None):
    """
    Подключается по SSH к серверу под администратором, скачивает актуальную
    серверную часть Arlene Colloquium из официального репозитория
    (REPO_URL) и запускает её как systemd-сервис на 0.0.0.0:port.

    progress_cb(str) - необязательный колбэк для промежуточных статусов.

    Возвращает (True, сообщение) при успехе или (False, сообщение об ошибке).

    Требования к удалённой машине: Linux (Debian/Ubuntu-подобный), SSH-доступ
    по паролю, у admin_user должны быть права на sudo, доступ в интернет
    (чтобы скачать репозиторий с GitHub).
    """

    def report(msg):
        if progress_cb:
            progress_cb(msg)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        report('Подключение по SSH...')
        ssh.connect(
            host, username=admin_user, password=admin_password,
            timeout=15, banner_timeout=15, auth_timeout=15,
        )
    except Exception as e:
        return False, f"Не удалось подключиться по SSH: {e}"

    try:
        report('Проверка Python и Git на сервере...')
        code, _, _ = _run(ssh, 'python3 --version && git --version')

        if code != 0:
            report('Устанавливаю Python3 и Git...')
            code, out, err = _run(
                ssh,
                'apt-get update && apt-get install -y python3 python3-pip python3-venv git',
                password=admin_password, use_sudo=True, timeout=600,
            )

            if code != 0:
                return False, f"Не удалось установить Python3/Git: {err or out}"

        report(f'Скачивание сервера из {REPO_URL}...')
        code, out, err = _run(
            ssh,
            f'rm -rf {REMOTE_REPO_DIR} && git clone --depth 1 {REPO_URL} {REMOTE_REPO_DIR}',
            timeout=180,
        )

        if code != 0:
            return False, f"Не удалось скачать репозиторий с GitHub: {err or out}"

        remote_server_dir = posixpath.join(REMOTE_REPO_DIR, REMOTE_SERVER_SUBDIR)

        report('Настройка HOST/PORT...')
        sftp = ssh.open_sftp()
        try:
            remote_server_py = posixpath.join(remote_server_dir, 'server.py')

            with sftp.file(remote_server_py, 'r') as f:
                server_source = f.read().decode('utf-8')

            server_source = _patch_host_port(server_source, port)

            with sftp.file(remote_server_py, 'w') as f:
                f.write(server_source)
        except Exception as e:
            return False, f"Не найден server.py в скачанном репозитории: {e}"
        finally:
            sftp.close()

        report('Установка зависимостей (может занять пару минут)...')
        code, out, err = _run(
            ssh,
            f'cd {remote_server_dir} && python3 -m pip install -r requirements.txt --break-system-packages',
            timeout=900,
        )

        python_bin = 'python3'

        if code != 0:
            report('Пробую установить зависимости через виртуальное окружение...')
            code, out, err = _run(
                ssh,
                f'cd {remote_server_dir} && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt',
                timeout=900,
            )

            if code != 0:
                return False, f"Не удалось установить зависимости: {err or out}"

            python_bin = f'/home/{admin_user}/{remote_server_dir}/venv/bin/python3'

        report('Настройка автозапуска (systemd)...')

        service_content = (
            "[Unit]\n"
            "Description=Arlene Colloquium Server\n"
            "After=network.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"WorkingDirectory=/home/{admin_user}/{remote_server_dir}\n"
            f"ExecStart={python_bin} /home/{admin_user}/{remote_server_dir}/server.py\n"
            "Restart=always\n"
            f"User={admin_user}\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )

        remote_service_tmp = posixpath.join(REMOTE_REPO_DIR, f'{SERVICE_NAME}.service')

        sftp = ssh.open_sftp()
        try:
            with sftp.file(remote_service_tmp, 'w') as f:
                f.write(service_content)
        finally:
            sftp.close()

        code, out, err = _run(
            ssh, f'mv {remote_service_tmp} /etc/systemd/system/{SERVICE_NAME}.service',
            password=admin_password, use_sudo=True,
        )

        if code != 0:
            return False, f"Не удалось установить systemd-юнит: {err or out}"

        code, out, err = _run(
            ssh,
            f'systemctl daemon-reload && systemctl enable --now {SERVICE_NAME}',
            password=admin_password, use_sudo=True, timeout=60,
        )

        if code != 0:
            return False, f"Не удалось запустить сервис: {err or out}"

        report('Проверка, что сервер поднялся...')
        time.sleep(3)

        if ping_server(host, port, timeout=6):
            return True, f"Сервер успешно установлен из {REPO_URL} и запущен на {host}:{port}"

        return True, (
            f"Сервис {SERVICE_NAME} установлен и запущен, но порт {port} пока "
            f"не отвечает - проверьте firewall/сеть на сервере."
        )
    finally:
        ssh.close()
