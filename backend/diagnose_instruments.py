import csv
import gzip
import io
import httpx
import asyncio

async def diagnose():
    url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz"
    print(f"Downloading {url}...")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        content = gzip.decompress(response.content)
        text_content = content.decode('utf-8')
        
    print("Download complete. Parsing headers from first line of content...")
    
    # Manually split lines to avoid CSV reader buffer issues if any
    lines = text_content.splitlines()
    if lines:
        headers = lines[0]
        print(f"RAW HEADERS: {headers}")
        
        reader = csv.DictReader(io.StringIO(text_content))
        print(f"Parsed Fieldnames: {reader.fieldnames}")
        
        try:
            first_row = next(reader)
            print("First Row Dict:")
            for k, v in first_row.items():
                print(f"  {k}: {v}")
        except:
            pass
            
    # Search for first FO item to see its structure
    print("\nScanning for first NSE_FO item...")
    reader = csv.DictReader(io.StringIO(text_content))
    for row in reader:
        if row.get('exchange') == 'NSE_FO':
            print("First NSE_FO Found:")
            for k, v in row.items():
                print(f"  {k}: {v}")
            break

if __name__ == "__main__":
    asyncio.run(diagnose())
