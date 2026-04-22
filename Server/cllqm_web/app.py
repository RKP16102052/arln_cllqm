from flask import Flask, render_template, send_from_directory, abort
from flask import request, redirect
import os

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(app.root_path, 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

DOWNLOAD_FILE_NAME_ANDROID = 'arlene_colloquim-0.9.1-arm64-v8a_armeabi-v7a-debug.apk'
DOWNLOAD_FILE_NAME_WINDOWS = 'arlene_colloquim-0.9-amd64.exe'
DOWNLOAD_FILE_NAME_LINUX = 'arlene_colloquim-0.9-amd64.tar.gz'

android_file_path = os.path.join(DOWNLOAD_FOLDER, DOWNLOAD_FILE_NAME_ANDROID)
windows_file_path = os.path.join(DOWNLOAD_FOLDER, DOWNLOAD_FILE_NAME_WINDOWS)
linux_file_path = os.path.join(DOWNLOAD_FOLDER, DOWNLOAD_FILE_NAME_LINUX)

WINDOWS_URL = 'https://github.com/RKP16102052/arln_cllqm/releases/download/Colloquium_v0.9_beta/arlene_colloquim-0.9.1-amd64.exe'
ANDROID_URL = 'https://github.com/RKP16102052/arln_cllqm/releases/download/Colloquium_v0.9_beta/arlene_colloquim-0.9.1-arm64-v8a_armeabi-v7a-debug.apk'
LINUX_URL = 'https://github.com/RKP16102052/arln_cllqm/releases/latest/download/'

if not os.path.exists(sample_file_path):
    with open(sample_file_path, 'w') as f:
        f.write("This is a placeholder for Arlene Colloquium installer.\nReplace with real binary.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/download')
def download_auto():
    user_agent = request.headers.get('User-Agent', '').lower()

    if 'android' in user_agent:
        return redirect('/download_android')

    elif 'windows' in user_agent:
        return redirect('/download_windows')

    elif 'linux' in user_agent:
        return redirect('/download_linux')

    return render_template('download.html')

@app.route('/download_android')
def download_android_file():
    return redirect(ANDROID_URL)

@app.route('/download_windows')
def download_windows_file():
    return redirect(WINDOWS_URL)

@app.route('/download_linux')
def download_windows_file():
    return redirect(LINUX_URL)


if __name__ == '__main__':
    app.run(host='130.12.45.26', port=5901, debug=False)
