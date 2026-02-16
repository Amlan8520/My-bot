import os
import threading
import pyotp
import pandas as pd
import pandas_ta as ta
from flask import Flask, render_template_string, jsonify
from SmartApi.smartConnect import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

# --- CONFIGURATION ---
API_KEY = "9SGXH14t"
CLIENT_ID = "C51790644"
PWD = "8486"
TOTP_SECRET = "KFFKBVAG7DW3UD5G7R3NWR7ZSY"

app = Flask(__name__)

# Live Tracking Data
data_store = {
    "ltp": 0.0,
    "rsi": 0.0,
    "status": "Initializing...",
    "signal": "WAITING FOR SIGNAL",
    "last_trade": "None"
}
prices = []

# --- ANGEL ONE ENGINE ---
obj = SmartConnect(api_key=API_KEY)
token = pyotp.TOTP(TOTP_SECRET).now()
res = obj.generateSession(CLIENT_ID, PWD, token)
feed_token = obj.getfeedToken()

sws = SmartWebSocketV2(res['data']['jwtToken'], API_KEY, CLIENT_ID, feed_token)

def on_data(wsapp, msg):
    global data_store, prices
    if 'last_traded_price' in msg:
        ltp = msg['last_traded_price'] / 100
        data_store["ltp"] = ltp
        data_store["status"] = "🟢 LIVE FEED CONNECTED"
        
        prices.append(ltp)
        if len(prices) > 14:
            df = pd.DataFrame(prices, columns=['close'])
            rsi = ta.rsi(df['close'], length=14).iloc[-1]
            data_store["rsi"] = round(rsi, 2)
            
            # AUTO-SIGNAL LOGIC
            if rsi < 30:
                data_store["signal"] = "🔥 BUY CALL (BOTTOM FOUND)"
            elif rsi > 70:
                data_store["signal"] = "⚠️ SELL / BOOK PROFIT"
            else:
                data_store["signal"] = "SCANNING MARKET..."
            
            if len(prices) > 50: prices.pop(0)

def on_open(wsapp):
    # Nifty Token (NSE Index)
    sws.subscribe("correlation_1", 1, 3, [{"exchangeType": 1, "tokens": ["99926000"]}])

threading.Thread(target=sws.connect, daemon=True).start()
sws.on_data = on_data
sws.on_open = on_open

# --- DASHBOARD HTML ---
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <title>Algo Dashboard</title>
</head>
<body class="bg-slate-900 text-white p-10">
    <div class="max-w-2xl mx-auto bg-slate-800 p-8 rounded-2xl border border-slate-700 shadow-2xl">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-bold text-blue-400">Trading Bot v1.0</h1>
            <span id="status" class="text-xs font-mono text-green-400">Connecting...</span>
        </div>
        
        <div class="grid grid-cols-2 gap-4 mb-6">
            <div class="bg-slate-700 p-4 rounded-lg">
                <p class="text-gray-400 text-sm">NIFTY LTP</p>
                <p id="ltp" class="text-3xl font-bold text-yellow-400">0.00</p>
            </div>
            <div class="bg-slate-700 p-4 rounded-lg">
                <p class="text-gray-400 text-sm">RSI (14)</p>
                <p id="rsi" class="text-3xl font-bold text-purple-400">0.0</p>
            </div>
        </div>

        <div class="bg-slate-900 p-4 rounded-lg border border-blue-500/30">
            <p class="text-xs text-blue-400 uppercase font-bold mb-1">Current Action</p>
            <p id="signal" class="text-xl font-mono">WAITING...</p>
        </div>
    </div>

    <script>
        async function update() {
            const r = await fetch('/api');
            const d = await r.json();
            document.getElementById('ltp').innerText = '₹ ' + d.ltp;
            document.getElementById('rsi').innerText = d.rsi;
            document.getElementById('signal').innerText = d.signal;
            document.getElementById('status').innerText = d.status;
        }
        setInterval(update, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def home(): return render_template_string(HTML)

@app.route('/api')
def api(): return jsonify(data_store)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
  
