from flask import Flask
import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return f"""
    <html>
        <body>
            <h1>🤖 Trading Bot</h1>
            <p>Working! Time: {datetime.datetime.now()}</p>
        </body>
    </html>
    """

if __name__ == '__main__':
    print("Starting server...")
    app.run(host='0.0.0.0', port=10000)
