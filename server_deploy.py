"""
Модуль отвечает за две вещи:
  1. ping_server(host, port)  - быстрая проверка, что по адресу уже кто-то
     слушает нужный порт (для добавления УЖЕ существующего сервера).
  2. deploy_new_server(...)   - установка и запуск серверной части Arlene
     Colloquium на чистой удалённой машине по SSH.

Установщик сам определяет дистрибутив (Debian/Ubuntu, RHEL/Fedora/CentOS,
Arch, openSUSE, Alpine) и использует соответствующий пакетный менеджер.
Больше не падает с 'command not found: apt' или
'ensurepip is not available'.
"""

import posixpath
import socket
import time

import paramiko


REPO_URL = 'https://github.com/RKP16102052/arln_cllqm.git'
REMOTE_REPO_DIR = 'arlene_repo'
REMOTE_SERVER_SUBDIR = 'Server'
SERVICE_NAME = 'arlene-server'


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def ping_server(host, port, timeout=4):
    """True, если по адресу host:port кто-то принимает TCP-соединения."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _run(ssh, command, password=None, use_sudo=False, timeout=120):
    """Выполняет команду на удалённой машине.

    use_sudo=True оборачивает команду в `sudo -S bash -c '...'` и подаёт
    пароль в stdin (чтобы не подвешивать SSH на запросе пароля).
    """
    if use_sudo:
        # Экранируем одинарные кавычки, чтобы внутренняя команда не сломалась
        safe = command.replace("'", "'\\''")
        full_command = "sudo -S -p '' bash -c '{}'".format(safe)
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


def _command_exists(ssh, name):
    code, out, _ = _run(ssh, 'command -v {} 2>/dev/null || true'.format(name))
    return code == 0 and out.strip() != ''


def _detect_os(ssh):
    """Определяет ОС и доступный пакетный менеджер.

    Возвращает dict:
      {
        'id': 'ubuntu' | 'debian' | 'fedora' | 'arch' | 'alpine' | ...,
        'id_like': 'debian' | 'rhel' | 'arch' | 'suse' | '',
        'pm': 'apt' | 'dnf' | 'yum' | 'pacman' | 'zypper' | 'apk' | None,
      }
    """
    os_id, os_like = '', ''

    code, out, _ = _run(ssh, 'cat /etc/os-release 2>/dev/null || true')
    if out:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('ID='):
                os_id = line.split('=', 1)[1].strip().strip('"').lower()
            elif line.startswith('ID_LIKE='):
                os_like = line.split('=', 1)[1].strip().strip('"').lower()

    info = {'id': os_id, 'id_like': os_like, 'pm': None}

    # Alpine — отдельный случай: у него и пакеты, и пути не как у всех
    if _command_exists(ssh, 'apk'):
        info['pm'] = 'apk'
        return info

    # Пробуем найти привычные пакетные менеджеры в порядке приоритета
    for pm in ('apt-get', 'dnf', 'yum', 'pacman', 'zypper'):
        if _command_exists(ssh, pm):
            info['pm'] = pm.replace('-get', '')
            return info

    return info


def _install_system_packages(ssh, password, os_info, progress_cb=None):
    """Ставит базовые пакеты (python3, pip, git, venv) под нужный дистрибутив.

    Возвращает True, если установка прошла (или менеджер пакетов не найден).
    """
    def report(msg):
        if progress_cb:
            progress_cb(msg)

    pm = os_info['pm']

    if pm is None:
        report('Не удалось определить пакетный менеджер, пропускаю установку системных пакетов.')
        return True

    # Набор пакетов для каждого менеджера
    packages = {
        'apt':    ['python3', 'python3-pip', 'python3-venv', 'git'],
        'dnf':    ['python3', 'python3-pip', 'git'],
        'yum':    ['python3', 'python3-pip', 'git'],
        'pacman': ['python', 'python-pip', 'git'],
        'zypper': ['python3', 'python3-pip', 'git'],
        'apk':    ['python3', 'py3-pip', 'git', 'py3-virtualenv'],
    }[pm]

    pkg_str = ' '.join(packages)

    if pm == 'apt':
        cmd = (
            'apt-get update -y && '
            'DEBIAN_FRONTEND=noninteractive apt-get install -y ' + pkg_str
        )
    elif pm == 'dnf':
        cmd = 'dnf install -y ' + pkg_str
    elif pm == 'yum':
        cmd = 'yum install -y ' + pkg_str
    elif pm == 'pacman':
        cmd = 'pacman -Sy --noconfirm ' + pkg_str
    elif pm == 'zypper':
        cmd = 'zypper --non-interactive install ' + pkg_str
    elif pm == 'apk':
        cmd = 'apk add --no-cache ' + pkg_str
    else:
        return True

    report(f'Устанавливаю системные пакеты ({pm}): {pkg_str}...')
    code, out, err = _run(
        ssh, cmd, password=password, use_sudo=True, timeout=900,
    )

    if code != 0:
        # Не валим всё: возможно часть уже стоит, а какая-то мелочь отвалилась
        report(f'Предупреждение: установка пакетов вернула код {code}.')
        # Ошибку не возвращаем — попробуем идти дальше, может этого хватит
        return True

    return True


def _create_venv(ssh, password, venv_path, os_info, progress_cb=None):
    """Создаёт venv в venv_path и возвращает путь к python-интерпретатору.

    Пробует несколько способов:
      1. `python3 -m venv <path>`
      2. `python3 -m venv --without-pip <path>` + bootstrap get-pip.py
      3. `python3 -m virtualenv <path>`
    """

    def report(msg):
        if progress_cb:
            progress_cb(msg)

    py = 'python3' if os_info['pm'] != 'pacman' else 'python'
    py_in_venv = f'{venv_path}/bin/python3'

    # --- Способ 1: обычный venv -----------------------------------------
    report(f'Создаю виртуальное окружение в {venv_path}...')
    _run(ssh, f'rm -rf {venv_path}')
    _run(ssh, f'{py} -m venv {venv_path} 2>&1 || true', timeout=300)

    code, out, _ = _run(ssh, f'test -x {py_in_venv} && echo ok || echo no')
    if 'ok' in out:
        return py_in_venv

    # --- Способ 2: venv --without-pip + get-pip.py ----------------------
    report('Стандартный venv не сработал, пробую --without-pip...')
    _run(ssh, f'rm -rf {venv_path}')
    _run(ssh, f'{py} -m venv --without-pip {venv_path} 2>&1 || true', timeout=300)

    code, out, _ = _run(ssh, f'test -x {py_in_venv} && echo ok || echo no')
    if 'ok' in out:
        report('Ставлю pip внутри venv...')
        _run(ssh, f'{py} -m ensurepip --upgrade 2>/dev/null || true')
        _run(
            ssh,
            f'curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py '
            f'&& {py_in_venv} /tmp/get-pip.py 2>&1 || true',
            timeout=300,
        )
        code, out, _ = _run(ssh, f'{py_in_venv} -m pip --version || true')
        if 'pip' in out:
            return py_in_venv

    # --- Способ 3: virtualenv -------------------------------------------
    report('Пробую virtualenv...')
    _run(ssh, f'rm -rf {venv_path}')
    _run(
        ssh,
        f'{py} -m pip install --upgrade virtualenv 2>/dev/null '
        f'|| pip3 install --upgrade virtualenv 2>/dev/null || true',
        timeout=300,
    )
    _run(ssh, f'{py} -m virtualenv {venv_path} 2>&1 || true', timeout=300)

    code, out, _ = _run(ssh, f'test -x {py_in_venv} && echo ok || echo no')
    if 'ok' in out:
        return py_in_venv

    raise RuntimeError(
        'Не удалось создать виртуальное окружение. '
        'Проверь, что на сервере установлен python3-venv (или аналог для твоей ОС).'
    )


def _patch_host_port(server_py_source, port):
    """Подменяет HOST/PORT в server.py, чтобы сервер слушал 0.0.0.0:port."""
    new_lines = []
    for line in server_py_source.splitlines():
        stripped = line.strip()
        if stripped.startswith('HOST '):
            new_lines.append("HOST = '0.0.0.0'")
        elif stripped.startswith('PORT '):
            new_lines.append(f'PORT = {port}')
        else:
            new_lines.append(line)
    return '\n'.join(new_lines) + '\n'


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------

def deploy_new_server(host, admin_user, admin_password, port=8765, progress_cb=None):
    """
    Подключается по SSH к серверу под администратором, скачивает серверную
    часть Arlene Colloquium из официального репозитория и запускает её как
    systemd-сервис на 0.0.0.0:port.

    progress_cb(str) - необязательный колбэк для промежуточных статусов.

    Возвращает (True, сообщение) при успехе или (False, сообщение об ошибке).
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
        return False, f'Не удалось подключиться по SSH: {e}'

    try:
        # ----- 1. Определяем ОС и пакетный менеджер ----------------------
        report('Определяю операционную систему...')
        os_info = _detect_os(ssh)
        report(f"ОС: {os_info['id'] or 'unknown'}, "
               f"пакетный менеджер: {os_info['pm'] or 'не определён'}")

        # ----- 2. Ставим системные пакеты (python3/pip/git/venv) ---------
        if not (_command_exists(ssh, 'python3') and _command_exists(ssh, 'git')):
            _install_system_packages(ssh, admin_password, os_info, report)
        else:
            report('Python3 и Git уже установлены, пропускаю.')

        # ----- 3. Определяем HOME администратора -------------------------
        # (важно: для root это /root, а не /home/root)
        code, home_dir, _ = _run(ssh, 'echo $HOME')
        home_dir = home_dir.strip() or f'/home/{admin_user}'
        remote_repo_path = posixpath.join(home_dir, REMOTE_REPO_DIR)
        remote_server_dir = posixpath.join(remote_repo_path, REMOTE_SERVER_SUBDIR)

        # ----- 4. Клонируем репозиторий ----------------------------------
        report(f'Скачиваю сервер из {REPO_URL}...')
        code, out, err = _run(
            ssh,
            f'rm -rf {remote_repo_path} && '
            f'git clone --depth 1 {REPO_URL} {remote_repo_path}',
            timeout=300,
        )
        if code != 0:
            return False, f'Не удалось скачать репозиторий с GitHub: {err or out}'

        # ----- 5. Патчим server.py под нужный порт -----------------------
        report('Настраиваю HOST/PORT в server.py...')
        sftp = ssh.open_sftp()
        try:
            remote_server_py = posixpath.join(remote_server_dir, 'server.py')
            with sftp.file(remote_server_py, 'r') as f:
                server_source = f.read().decode('utf-8')
            server_source = _patch_host_port(server_source, port)
            with sftp.file(remote_server_py, 'w') as f:
                f.write(server_source)
        except Exception as e:
            return False, f'Не найден server.py в скачанном репозитории: {e}'
        finally:
            sftp.close()

        # ----- 6. Создаём venv и ставим зависимости ----------------------
        report('Создаю виртуальное окружение...')
        try:
            venv_path = posixpath.join(remote_server_dir, 'venv')
            python_bin = _create_venv(ssh, admin_password, venv_path, os_info, report)
        except RuntimeError as e:
            return False, str(e)

        report('Ставлю зависимости (может занять пару минут)...')
        code, out, err = _run(
            ssh,
            f'cd {remote_server_dir} && '
            f'{python_bin} -m pip install --upgrade pip setuptools wheel && '
            f'{python_bin} -m pip install -r requirements.txt',
            timeout=1200,
        )
        if code != 0:
            return False, f'Не удалось установить зависимости: {err or out}'

        # ----- 7. Готовим systemd unit ----------------------------------
        report('Настраиваю автозапуск (systemd)...')

        service_content = (
            '[Unit]\n'
            'Description=Arlene Colloquium Server\n'
            'After=network.target\n\n'
            '[Service]\n'
            'Type=simple\n'
            f'WorkingDirectory={remote_server_dir}\n'
            f'ExecStart={python_bin} {remote_server_dir}/server.py\n'
            'Restart=always\n'
            f'User={admin_user}\n\n'
            '[Install]\n'
            'WantedBy=multi-user.target\n'
        )

        remote_service_tmp = posixpath.join(home_dir, f'{SERVICE_NAME}.service')
        sftp = ssh.open_sftp()
        try:
            with sftp.file(remote_service_tmp, 'w') as f:
                f.write(service_content)
        finally:
            sftp.close()

        code, out, err = _run(
            ssh,
            f'mv {remote_service_tmp} /etc/systemd/system/{SERVICE_NAME}.service',
            password=admin_password, use_sudo=True,
        )
        if code != 0:
            return False, f'Не удалось установить systemd-юнит: {err or out}'

        code, out, err = _run(
            ssh,
            f'systemctl daemon-reload && '
            f'systemctl enable --now {SERVICE_NAME}',
            password=admin_password, use_sudo=True, timeout=60,
        )
        if code != 0:
            return False, f'Не удалось запустить сервис: {err or out}'

        # ----- 8. Проверяем, что сервер поднялся ------------------------
        report('Проверяю, что сервер отвечает на порту...')
        for _ in range(6):
            time.sleep(1)
            if ping_server(host, port, timeout=3):
                return True, (
                    f'Сервер успешно установлен из {REPO_URL} '
                    f'и запущен на {host}:{port}'
                )

        # Порт не отвечает — вернём кусок лога journalctl для диагностики
        code, log_out, _ = _run(
            ssh,
            f'journalctl -u {SERVICE_NAME} -n 25 --no-pager 2>/dev/null || true',
        )
        return False, (
            f'Сервис установлен, но порт {port} не отвечает. '
            f'Проверь firewall сервера.\n\n'
            f'Последние строки лога:\n{log_out[-800:]}'
        )

    finally:
        ssh.close()
