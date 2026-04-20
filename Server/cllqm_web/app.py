from flask import Flask, render_template, send_from_directory, abort
import os

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(app.root_path, 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

DOWNLOAD_FILE_NAME = 'ui.py'   # или .exe, .dmg, .py

sample_file_path = os.path.join(DOWNLOAD_FOLDER, DOWNLOAD_FILE_NAME)
if not os.path.exists(sample_file_path):
    with open(sample_file_path, 'w') as f:
        f.write("This is a placeholder for Arlene Colloquium installer.\nReplace with real binary.")

@app.route('/')
def index():
    return render_template('index.html', filename=DOWNLOAD_FILE_NAME)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/download')
def download_file():
    try:
        return send_from_directory(
            DOWNLOAD_FOLDER,
            DOWNLOAD_FILE_NAME,
            as_attachment=True,
            download_name=DOWNLOAD_FILE_NAME
        )
    except FileNotFoundError:
        abort(404, description="Файл не найден. Пожалуйста, сообщите администратору.")

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5901, debug=False)
