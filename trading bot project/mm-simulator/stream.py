import json
import threading
import time
import websocket

class BinanceStreamer:
    def __init__(self, symbol="btcusdt"):
        self.symbol = symbol.lower()
        self.ws_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@depth20@100ms"
        
        # Shared state that the engine/dashboard will read
        self.best_bid = None
        self.best_ask = None
        self.ofi = 0.0
        self.microprice = None
        
        self.ws = None
        self.thread = None
        self.is_running = False

    def _on_message(self, ws, message):
        data = json.loads(message)
        # depth20 gives top 20 bids/asks arrays [[price, qty], ...]
        if 'bids' in data and 'asks' in data:
            if len(data['bids']) == 0 or len(data['asks']) == 0:
                return
                
            self.best_bid = float(data['bids'][0][0])
            self.best_ask = float(data['asks'][0][0])
            
            # Sum up top 20 levels of volume
            bid_vol = sum(float(b[1]) for b in data['bids'])
            ask_vol = sum(float(a[1]) for a in data['asks'])
            
            total_vol = bid_vol + ask_vol
            if total_vol > 0:
                self.ofi = (bid_vol - ask_vol) / total_vol
                self.microprice = (ask_vol * self.best_bid + bid_vol * self.best_ask) / total_vol
            else:
                self.ofi = 0.0
                self.microprice = (self.best_bid + self.best_ask) / 2.0

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
