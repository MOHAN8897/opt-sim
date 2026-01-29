
import requests
import json

def verify_chain():
    url = "http://localhost:8000/api/market/option-chain"
    # Using the token from recent logs
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJtb2hhbnNhaXRlamEuOTlAZ21haWwuY29tIiwiZXhwIjoxNzY4OTc4MjU1fQ.ZaAC3VmlZR-cxcbupgTiUy_NrxXO1QRh1alejwhXAZM"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    
    params = {
        "instrument_key": "NSE_INDEX|Nifty 50",
        "expiry_date": "2026-02-03" # From screenshot
    }
    
    print(f"Fetch URL: {url}")
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print("Response Keys:", data.keys())
            
            chain = data.get("chain", [])
            print(f"Chain Length: {len(chain)}")
            
            if len(chain) > 0:
                first = chain[0]
                print(f"\n--- First Row ---")
                print(f"Strike Price: {first.get('strike_price')} (Type: {type(first.get('strike_price'))})")
                print(f"Is ATM: {first.get('is_atm')}")
                
                ce = first.get("call_options", {})
                pe = first.get("put_options", {})
                
                print(f"CALL Key: {ce.get('instrument_key')}")
                print(f"CALL Symbol: {ce.get('trading_symbol')}")
                print(f"PUT Key: {pe.get('instrument_key')}")
                
                print(f"\n--- Keys check ---")
                print(f"Has 'strike_price'? {'strike_price' in first}")
                print(f"Has 'strike'? {'strike' in first}")
            else:
                print("⚠️ Chain is empty!")
                
        else:
            print(f"Error: {resp.text}")

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    verify_chain()
