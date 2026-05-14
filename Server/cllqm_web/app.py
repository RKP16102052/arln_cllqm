from flask import Flask, render_template, redirect, request

app = Flask(__name__)

ANDROID_URL = 'https://github.com/RKP16102052/arln_cllqm/releases/download/Colloquium_v0.9_beta/arlene_colloquim-0.9.1-arm64-v8a_armeabi-v7a-debug.apk'
WINDOWS_URL = 'https://github.com/RKP16102052/arln_cllqm/releases/download/Colloquium_v0.9_beta/arlene_colloquim-0.9.1-amd64.exe'
LINUX_URL = 'https://github.com/RKP16102052/arln_cllqm/releases/latest/download/arlene_colloquim-0.9-amd64.tar.gz'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download')
def download_auto():
    ua = request.headers.get('User-Agent', '').lower()
    if 'android' in ua:
        return redirect('/download_android')
    elif 'windows' in ua:
        return redirect('/download_windows')
    elif 'linux' in ua:
        return redirect('/download_linux')
    return render_template('choose_platform.html')

@app.route('/download_android')
def download_android():
    return render_template('redirect_with_download.html', download_url=ANDROID_URL, platform='android')

@app.route('/download_windows')
def download_windows():
    return render_template('redirect_with_download.html', download_url=WINDOWS_URL, platform='windows')

@app.route('/download_linux')
def download_linux():
    return render_template('redirect_with_download.html', download_url=LINUX_URL, platform='linux')

@app.route('/donate')
def donate():
    return render_template('donate.html')  # страница с криптокошельками, Boosty и благодарностью

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5901, debug=False)
