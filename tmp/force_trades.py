
import requests
import time

s = requests.Session()
# Login
print('Logging in...')
r = s.post('http://127.0.0.1:8080/api/v1/token', json={'username': 'freqtrader', 'password': 'SuperSecretPassword123'}, headers={'Content-Type': 'application/json'})
print('Login:', r.status_code)
if r.status_code == 200:
    token = r.json().get('access_token')
    s.headers.update({'Authorization': f'Bearer {token}'})
    
    pairs = ['BTC/USDC', 'ETH/USDC', 'SOL/USDC']
    for i in range(15):
        pair = pairs[i % 3]
        # Open trade
        r_open = s.post('http://127.0.0.1:8080/api/v1/forceenter', json={'pair': pair, 'ordertype': 'limit'})
        print(f'Trade {i+1} Enter ({pair}):', r_open.status_code)
        
        # Wait a short while so it registers as open before we close it
        time.sleep(2)
        
        # We need the trade_id to close it, let's get the status or just forceexit all!
        r_status = s.get('http://127.0.0.1:8080/api/v1/status')
        if r_status.status_code == 200:
            trades = r_status.json()
            for t in trades:
                if t['pair'] == pair:
                    t_id = t['trade_id']
                    r_close = s.post('http://127.0.0.1:8080/api/v1/forceexit', json={'tradeid': t_id, 'ordertype': 'limit'})
                    print(f'Trade {i+1} Exit ({pair}):', r_close.status_code)
        time.sleep(2)

