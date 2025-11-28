from flask import Flask, jsonify
import datetime
import time
import threading
import os

app = Flask(__name__)

# Простой счетчик для демонстрации
request_count = 0

@app.route('/')
def home():
    global request_count
    request_count += 1
    
    return f"""
    <html>
        <body>
            <h1>🤖 Trading Bot</h1>
            <p><strong>Status:</strong> ACTIVE ✅</p>
            <p><strong>Time:</strong> {datetime.datetime.now()}</p>
            <p><strong>Requests:</strong> {request_count}</p>
            <p><strong>Python:</strong> Working perfectly!</p>
            <p><a href="/status">JSON Status</a></p>
        </body>
    </html>
    """

@app.route('/status')
def status():
    return jsonify({
        "status": "active",
        "time": datetime.datetime.now().isoformat(),
        "environment": "Render",
        "bot": "trading-bot"
    })

@app.route('/health')
def health():
    return "OK"

def background_worker():
    """Фоновая задача"""
    while True:
        print(f"Background worker running at {datetime.datetime.now()}")
        time.sleep(300)  # 5 минут

if __name__ == '__main__':
    # Запускаем фоновый поток
    worker_thread = threading.Thread(target=background_worker)
    worker_thread.daemon = True
    worker_thread.start()
    
    print("🚀 Trading Bot started successfully!")
    app.run(host='0.0.0.0', port=10000, debug=False)
