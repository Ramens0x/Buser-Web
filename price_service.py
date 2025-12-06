import requests
import time
from datetime import datetime, timedelta
from threading import Lock
import os

class PriceService:
    def __init__(self):
        # Cache để tránh spam request
        self.cache = {
            'crypto_prices': {},  # {symbol: {'price': float, 'timestamp': datetime}}
            'usd_vnd_rate': None,
            'usd_vnd_timestamp': None
        }
        self.cache_lock = Lock()
        
        # Cấu hình spread (biên độ mua/bán)
        self.spread_config = {
            'ether': {'buy': 1.015, 'sell': 0.985},
            'bustabit': {'buy': 1.015, 'sell': 0.985},  # +1.5% mua, -1.5% bán
            'btc': {'buy': 1.015, 'sell': 0.985},
            'usdt': {'buy': 1.01, 'sell': 0.99},        # +1% mua, -1% bán
            'eth': {'buy': 1.015, 'sell': 0.985},
            'bnb': {'buy': 1.015, 'sell': 0.985},
            'sol': {'buy': 1.015, 'sell': 0.985}
        }
        
        # Timeout cho cache
        self.crypto_cache_seconds = 60  # 60 giây
        self.forex_cache_seconds = 3600  # 1 giờ
        
        # Danh sách API forex (fallback)
        self.forex_apis = [
            {
                'name': 'ExchangeRate-API',
                'url': 'https://api.exchangerate-api.com/v4/latest/USD',
                'extract': lambda data: data['rates']['VND']
            },
            {
                'name': 'Fixer.io Backup',
                'url': 'https://open.er-api.com/v6/latest/USD',
                'extract': lambda data: data['rates']['VND']
            }
        ]
        
        # Map coin symbols
        self.coin_map = {
            'ether': 'ETHUSDT',
            'bustabit': 'BTCUSDT',  # Bustabit = Bitcoin
            'btc': 'BTCUSDT',
            'bitcoin': 'BTCUSDT',
            'usdt': 'USDTUSD',      # USDT → USD direct
            'eth': 'ETHUSDT',
            'ethereum': 'ETHUSDT',
            'bnb': 'BNBUSDT',
            'sol': 'SOLUSDT'
        }
        
        print("✅ PriceService initialized")

    def fetch_binance_price(self, symbol):
        """Lấy giá từ Binance API"""
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                price = float(data['price'])
                return price
            else:
                print(f"❌ Binance API error for {symbol}: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error fetching Binance price for {symbol}: {e}")
            return None

    def fetch_usd_vnd_rate(self):
        """Lấy tỷ giá USD → VND với fallback"""
        # Kiểm tra cache trước
        with self.cache_lock:
            if self.cache['usd_vnd_rate'] and self.cache['usd_vnd_timestamp']:
                age = (datetime.now() - self.cache['usd_vnd_timestamp']).seconds
                if age < self.forex_cache_seconds:
                    return self.cache['usd_vnd_rate']
        
        # Thử từng API forex
        for api_config in self.forex_apis:
            try:
                response = requests.get(api_config['url'], timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    vnd_rate = api_config['extract'](data)
                    
                    # Lưu vào cache
                    with self.cache_lock:
                        self.cache['usd_vnd_rate'] = vnd_rate
                        self.cache['usd_vnd_timestamp'] = datetime.now()
                    
                    print(f"✅ USD/VND rate updated: {vnd_rate:,.0f} ({api_config['name']})")
                    return vnd_rate
                    
            except Exception as e:
                print(f"⚠️ {api_config['name']} failed: {e}")
                continue
        
        # Nếu tất cả API đều fail, dùng giá trị cached cũ hoặc fallback
        with self.cache_lock:
            if self.cache['usd_vnd_rate']:
                print("⚠️ Using cached USD/VND rate")
                return self.cache['usd_vnd_rate']
        
        # Fallback cuối cùng: giá cố định
        print(f"⚠️ All forex APIs failed. Cannot update price.")
        return None 

    def get_crypto_price_usd(self, coin_key):
        """Lấy giá crypto theo USD (có cache)"""
        coin_key = coin_key.lower()
        
        # Kiểm tra cache
        with self.cache_lock:
            if coin_key in self.cache['crypto_prices']:
                cached = self.cache['crypto_prices'][coin_key]
                age = (datetime.now() - cached['timestamp']).seconds
                if age < self.crypto_cache_seconds:
                    return cached['price']
        
        # Lấy symbol Binance
        binance_symbol = self.coin_map.get(coin_key)
        if not binance_symbol:
            print(f"❌ Unknown coin: {coin_key}")
            return None
        
        # Fetch từ Binance
        price_usd = self.fetch_binance_price(binance_symbol)
        if price_usd:
            # Lưu cache
            with self.cache_lock:
                self.cache['crypto_prices'][coin_key] = {
                    'price': price_usd,
                    'timestamp': datetime.now()
                }
            return price_usd
        
        # Retry 1 lần nếu fail
        time.sleep(0.5)
        price_usd = self.fetch_binance_price(binance_symbol)
        if price_usd:
            with self.cache_lock:
                self.cache['crypto_prices'][coin_key] = {
                    'price': price_usd,
                    'timestamp': datetime.now()
                }
        return price_usd

    def convert_to_vnd(self, coin_key, mode='mid'):
        """
        Convert giá crypto sang VND
        """
        coin_key = coin_key.lower()
        
        # Lấy giá USD
        price_usd = self.get_crypto_price_usd(coin_key)
        if not price_usd:
            return None
        
        # Lấy tỷ giá USD/VND
        usd_vnd = self.fetch_usd_vnd_rate()
        
        # Convert
        if coin_key == 'usdt':
            base_vnd = price_usd * usd_vnd
        elif coin_key in ['bustabit', 'bits', 'ether', 'ethos']:
            base_vnd = (price_usd * usd_vnd) / 1000000
        else:
            # BTC, ETH, etc. → USD → VND
            base_vnd = price_usd * usd_vnd
        
        # Áp dụng spread
        if mode == 'buy':
            spread = self.spread_config.get(coin_key, {}).get('buy', 1.015)
            return base_vnd * spread
        elif mode == 'sell':
            spread = self.spread_config.get(coin_key, {}).get('sell', 0.985)
            return base_vnd * spread
        else:
            return base_vnd

    def get_rate_buy_sell(self, coin_key):
        """Trả về giá mua/bán"""
        buy_price = self.convert_to_vnd(coin_key, mode='buy')
        sell_price = self.convert_to_vnd(coin_key, mode='sell')
        
        if buy_price and sell_price:
            return {
                'coin': coin_key,
                'buy': round(buy_price, 2),
                'sell': round(sell_price, 2),
                'timestamp': datetime.now().isoformat()
            }
        return None

    def get_all_prices(self):

        result = {}
        target_coins = ['bustabit', 'ether', 'btc', 'usdt', 'eth', 'bnb', 'sol'] 
        for coin in target_coins:
            rates = self.get_rate_buy_sell(coin)
            if rates:
                result[coin] = {'buy': rates['buy'], 'sell': rates['sell']}
        return result

    def update_spread(self, coin_key, buy_percent, sell_percent):
        """Cập nhật spread cho coin"""
        coin_key = coin_key.lower()
        self.spread_config[coin_key] = {
            'buy': 1 + (buy_percent / 100),
            'sell': 1 - (sell_percent / 100)
        }
        print(f"✅ Updated spread for {coin_key}: buy={buy_percent}%, sell={sell_percent}%")

def fetch_binance_price(self, symbol, retries=3):
    for attempt in range(retries):
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return float(data['price'])
            else:
                print(f"❌ Binance API error for {symbol}: {response.status_code}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
                
        except Exception as e:
            print(f"❌ Error fetching Binance price for {symbol}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            continue
    
    return None

price_service = PriceService()