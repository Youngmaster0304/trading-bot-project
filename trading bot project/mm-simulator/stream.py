import json
import threading
import time
import websocket

class BinanceStreamer:
    def __init__(self, symbols=["btcusdt", "ethusdt"]):
        self.symbols = [s.lower() for s in symbols]
        
        # Build multiplexed stream URL
        streams = "/".join([f"{s}@depth20@100ms" for s in self.symbols])
        self.ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        
        # Shared state dictionaries mapped by symbol
        self.best_bid = {s: None for s in self.symbols}
        self.best_ask = {s: None for s in self.symbols}
        self.ofi = {s: 0.0 for s in self.symbols}
        self.microprice = {s: None for s in self.symbols}
        
        self.ws = None
        self.thread = None
        self.is_running = False

    def _on_message(self, ws, message):
        raw = json.loads(message)
        
        # Combined stream wraps the payload in "data" and identifies it by "stream"
        if 'stream' not in raw or 'data' not in raw:
            return
            
        stream_name = raw['stream']
        symbol = stream_name.split('@')[0]
        data = raw['data']
        
        # depth20 gives top 20 bids/asks arrays [[price, qty], ...]
        if 'bids' in data and 'asks' in data:
            if len(data['bids']) == 0 or len(data['asks']) == 0:
                return
                
            best_bid = float(data['bids'][0][0])
            best_ask = float(data['asks'][0][0])
            
            self.best_bid[symbol] = best_bid
            self.best_ask[symbol] = best_ask
            
            # Sum up top 20 levels of volume
            bid_vol = sum(float(b[1]) for b in data['bids'])
            ask_vol = sum(float(a[1]) for a in data['asks'])
            
            total_vol = bid_vol + ask_vol
            if total_vol > 0:
                self.ofi[symbol] = (bid_vol - ask_vol) / total_vol
                self.microprice[symbol] = (ask_vol * best_bid + bid_vol * best_ask) / total_vol
            else:
                self.ofi[symbol] = 0.0
                self.microprice[symbol] = (best_bid + best_ask) / 2.0

    def _on_error(self, ws, error):
        print(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print("WebSocket closed")
        
    def _on_open(self, ws):
        print(f"WebSocket multiplexed explicitly opened for {self.symbols}")

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
        
        # Wait until we receive the first tick for ALL symbols
        while any(b is None for b in self.best_bid.values()) and self.is_running:
            time.sleep(0.1)

    def stop(self):
        self.is_running = False
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=1.0)
