import json
import threading
import time
import websocket

class BinanceStreamer:
    def __init__(self, symbol="btcusdt"):
        self.symbol = symbol.lower()
        self.ws_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@bookTicker"
        
        # Shared state that the engine/dashboard will read
        self.best_bid = None
        self.best_ask = None
        
        self.ws = None
        self.thread = None
        self.is_running = False

    def _on_message(self, ws, message):
        data = json.loads(message)
        # bookTicker gives best bid/ask
        if 'b' in data and 'a' in data:
            self.best_bid = float(data['b'])
            self.best_ask = float(data['a'])

    def _on_error(self, ws, error):
        print(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print("WebSocket closed")
        
    def _on_open(self, ws):
        print(f"WebSocket explicitly opened for {self.symbol}")

    def start(self):
        self.is_running = True
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.thread.start()
        
        # Wait until we receive the first tick
        while self.best_bid is None and self.is_running:
            time.sleep(0.1)

    def stop(self):
        self.is_running = False
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=1.0)
