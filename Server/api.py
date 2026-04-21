from flask import Flask, request, jsonify
from server import (reg_verification, fin_reg, login, create_chat_with_user, create_group, get_public_key,
                   send_message, get_messages, get_name, get_chats, get_members_keys, upload_avatar,
                   download_avatar, download_chat_image, upload_file, download_file, send_file)


app = Flask(__name__)


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = reg_verification(data)

    return jsonify(fin)


@app.route('/api/register_verification', methods=['POST'])
def register_verification():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = fin_reg(data)

    return jsonify(fin)


@app.route('/api/login', methods=['POST'])
def web_login():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = login(data)

    return jsonify(fin)


@app.route('/api/create_chat', methods=['POST'])
def create_chat():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = create_chat_with_user(data)

    return jsonify(fin)


@app.route('/api/create_group', methods=['POST'])
def web_create_group():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = create_group(data)

    return jsonify(fin)


@app.route('/api/get_public_key', methods=['POST'])
def web_get_public_key():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = get_public_key(data)

    return jsonify(fin)


@app.route('/api/send_message', methods=['POST'])
def web_send_message():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = send_message(data)

    return jsonify(fin)


@app.route('/api/get_messages', methods=['POST'])
def web_get_messages():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = get_messages(data)

    return jsonify(fin)


@app.route('/api/get_name', methods=['POST'])
def web_get_name():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = get_name(data)

    return jsonify(fin)


@app.route('/api/get_chats', methods=['POST'])
def web_get_chats():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = get_chats(data)

    return jsonify(fin)


@app.route('/api/get_members_keys', methods=['POST'])
def web_get_members_keys():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = get_members_keys(data)

    return jsonify(fin)


@app.route('/api/gupload_avatar', methods=['POST'])
def web_upload_avatar():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = upload_avatar(data)

    return jsonify(fin)


@app.route('/api/download_avatar', methods=['POST'])
def web_download_avatar():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = download_avatar(data)

    return jsonify(fin)


@app.route('/api/download_chat_image', methods=['POST'])
def web_download_chat_image():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = download_chat_image(data)

    return jsonify(fin)


@app.route('/api/upload_file', methods=['POST'])
def web_upload_file():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = upload_file(data)

    return jsonify(fin)


@app.route('/api/download_file', methods=['POST'])
def web_download_file():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = download_file(data)

    return jsonify(fin)


@app.route('/api/send_file', methods=['POST'])
def web_send_file():
    data = request.json

    if not data:
        fin = {'status': 'error', 'message': 'Нет данных'}
    else:
        fin = send_file(data)

    return jsonify(fin)


if __name__ == '__main__':
    app.run(port=8080, host='127.0.0.1')