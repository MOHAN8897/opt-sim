import csv
import gzip
import io
import httpx
import asyncio

async def debug_nifty():
    url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz"
    print(f"Downloading {url}...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url)
        content = gzip.decompress(response.content)
        text_content = content.decode('utf-8')
        
    reader = csv.DictReader(io.StringIO(text_content))
    
    # Search for NSE_INDEX items
    print("\n=== SEARCHING FOR NSE_INDEX ITEMS ===")
    nse_index_count = 0
    nifty_items = []
    
    for row in reader:
        if row.get('exchange') == 'NSE_INDEX':
            nse_index_count += 1
            name = row.get('name', '')
            instrument_key = row.get('instrument_key', '')
            
            if 'Nifty' in name or 'NIFTY' in name:
                nifty_items.append({
                    'name': name,
                    'instrument_key': instrument_key,
                    'tradingsymbol': row.get('tradingsymbol', '')
                })
                
            if nse_index_count <= 10:
                print(f"  {nse_index_count}. {name} -> {instrument_key}")
    
    print(f"\n✅ Total NSE_INDEX items found: {nse_index_count}")
    
    print(f"\n=== NIFTY RELATED INDEXES ({len(nifty_items)} found) ===")
    for item in nifty_items:
        print(f"  Name: {item['name']}")
        print(f"  Key: {item['instrument_key']}")
        print(f"  Symbol: {item['tradingsymbol']}")
        print()
    
    # Now search for OPTIDX options for NIFTY
    print("\n=== SEARCHING FOR NIFTY OPTIONS (OPTIDX) ===")
    reader = csv.DictReader(io.StringIO(text_content))
    nifty_options = []
    
    for row in reader:
        if row.get('exchange') == 'NSE_FO' and row.get('instrument_type') == 'OPTIDX':
            name = row.get('name', '')
            if name in ['NIFTY', 'Nifty 50', 'NIFTY 50']:
                nifty_options.append({
                    'name': name,
                    'tradingsymbol': row.get('tradingsymbol', ''),
                    'instrument_key': row.get('instrument_key', ''),
                    'expiry': row.get('expiry', ''),
                    'strike': row.get('strike', ''),
                    'option_type': row.get('option_type', '')
                })
                
                if len(nifty_options) <= 5:
                    print(f"  {len(nifty_options)}. Name: {name}, Symbol: {row.get('tradingsymbol')}, Expiry: {row.get('expiry')}, Strike: {row.get('strike')}")
    
    print(f"\n✅ Total NIFTY options found: {len(nifty_options)}")
    
    # Check what unique names are in OPTIDX
    reader = csv.DictReader(io.StringIO(text_content))
    optidx_names = set()
    for row in reader:
        if row.get('exchange') == 'NSE_FO' and row.get('instrument_type') == 'OPTIDX':
            optidx_names.add(row.get('name', ''))
    
    print(f"\n=== All Unique OPTIDX Names ({len(optidx_names)}) ===")
    for name in sorted(optidx_names):
        print(f"  - {name}")

if __name__ == "__main__":
    asyncio.run(debug_nifty())
