"""
Script kiểm tra hệ thống giá mới
Chạy: python test_price_service.py
"""
from price_service import price_service
import json
from datetime import datetime

def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_usd_vnd_rate():
    print_header("TEST 1: Lấy tỷ giá USD/VND")
    rate = price_service.fetch_usd_vnd_rate()
    print(f"✅ Tỷ giá: 1 USD = {rate:,.0f} VND")
    return rate

def test_crypto_prices_usd():
    print_header("TEST 2: Lấy giá Crypto gốc (USD)")
    
    coins = ['btc', 'usdt', 'eth', 'bnb', 'doge']
    results = {}
    
    for coin in coins:
        price = price_service.get_crypto_price_usd(coin)
        if price:
            results[coin] = price
            print(f"✅ {coin.upper()}: ${price:,.2f}")
        else:
            print(f"❌ {coin.upper()}: Failed to fetch")
    
    return results

def test_convert_to_vnd():
    print_header("TEST 3: Convert sang VND (với spread)")
    
    coins = ['bustabit', 'usdt', 'eth', 'bnb']
    
    for coin in coins:
        print(f"\n🪙 {coin.upper()}:")
        
        mid = price_service.convert_to_vnd(coin, mode='mid')
        buy = price_service.convert_to_vnd(coin, mode='buy')
        sell = price_service.convert_to_vnd(coin, mode='sell')
        
        if mid and buy and sell:
            print(f"   Giá gốc:  {mid:,.0f} VND")
            print(f"   Giá MUA:  {buy:,.0f} VND  (+{((buy/mid - 1)*100):.2f}%)")
            print(f"   Giá BÁN:  {sell:,.0f} VND  ({((sell/mid - 1)*100):.2f}%)")
        else:
            print(f"   ❌ Failed")

def test_get_rate_buy_sell():
    print_header("TEST 4: API get_rate_buy_sell")
    
    coins = ['bustabit', 'usdt', 'btc', 'eth']
    
    for coin in coins:
        rates = price_service.get_rate_buy_sell(coin)
        if rates:
            print(f"\n✅ {coin.upper()}:")
            print(f"   Mua:  {rates['buy']:,.0f} VND")
            print(f"   Bán:  {rates['sell']:,.0f} VND")
            print(f"   Time: {rates['timestamp']}")
        else:
            print(f"❌ {coin.upper()}: Failed")

def test_get_all_prices():
    print_header("TEST 5: API get_all_prices")
    
    all_prices = price_service.get_all_prices()
    print(json.dumps(all_prices, indent=2, ensure_ascii=False))

def test_cache():
    print_header("TEST 6: Cache Status")
    
    with price_service.cache_lock:
        print(f"USD/VND Rate: {price_service.cache['usd_vnd_rate']:,.0f}")
        print(f"USD/VND Timestamp: {price_service.cache['usd_vnd_timestamp']}")
        print(f"\nCrypto Cache:")
        
        for coin, data in price_service.cache['crypto_prices'].items():
            age = (datetime.now() - data['timestamp']).seconds
            print(f"  {coin.upper()}: ${data['price']:,.2f} (age: {age}s)")

def test_spread_update():
    print_header("TEST 7: Update Spread")
    
    print("Spread trước khi update:")
    print(f"  BTC: {price_service.spread_config['btc']}")
    
    # Test update
    price_service.update_spread('btc', buy_percent=2.0, sell_percent=2.0)
    
    print("\nSpread sau khi update:")
    print(f"  BTC: {price_service.spread_config['btc']}")
    
    # Reset về mặc định
    price_service.update_spread('btc', buy_percent=1.5, sell_percent=1.5)
    print("\n✅ Reset về mặc định")

def test_performance():
    print_header("TEST 8: Performance (Thời gian cache)")
    
    import time
    
    # Lần 1: Fetch từ API
    start = time.time()
    price1 = price_service.get_crypto_price_usd('btc')
    time1 = (time.time() - start) * 1000
    print(f"Lần 1 (Fetch API): {time1:.2f}ms | Price: ${price1:,.2f}")
    
    # Lần 2: Lấy từ cache
    start = time.time()
    price2 = price_service.get_crypto_price_usd('btc')
    time2 = (time.time() - start) * 1000
    print(f"Lần 2 (Cache):     {time2:.2f}ms | Price: ${price2:,.2f}")
    
    print(f"\n⚡ Cache nhanh hơn: {(time1/time2):.1f}x")

def run_all_tests():
    """Chạy tất cả tests"""
    print("\n")
    print("🚀 BẮT ĐẦU KIỂM TRA HỆ THỐNG GIÁ MỚI")
    print("="*60)
    
    try:
        test_usd_vnd_rate()
        test_crypto_prices_usd()
        test_convert_to_vnd()
        test_get_rate_buy_sell()
        test_get_all_prices()
        test_cache()
        test_spread_update()
        test_performance()
        
        print("\n")
        print("="*60)
        print("✅ TẤT CẢ TESTS HOÀN THÀNH!")
        print("="*60)
        print("\n💡 Hệ thống sẵn sàng!")
        
    except Exception as e:
        print(f"\n❌ LỖI: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()