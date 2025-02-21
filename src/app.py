from flask import Flask, render_template, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# 設定圖片上傳資料夾
app.config['UPLOAD_FOLDER'] = 'images'

# 確保圖片資料夾存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/style.css')
def serve_css():
    return send_file('style.css')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860, debug=True)
