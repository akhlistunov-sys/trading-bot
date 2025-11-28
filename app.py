from flask import Flask
import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return f"""
    <html>
        <body>
            <h1>🤖 Trading Bot</h1>
            <p><strong>Status:</strong> ACTIVE</p>
            <p><strong>Time:</strong> {datetime.datetime.now()}</p>
            <p><strong>Python:</strong> Working!</p>
        </body>
    </html>
    """

@app.route('/status')
def status():
    return {"status": "active", "time": datetime.datetime.now().isoformat()}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
