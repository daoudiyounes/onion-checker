import requests
import time
import csv
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import os

# === Configuration ===
INPUT_FILE = "onion_list.txt"     # Can be .txt, .csv, or .sqlite
SQLITE_TABLE = "onions"           # Used only if .sqlite
SQLITE_COLUMN = "url"             # Used only if .sqlite
TOR_PROXY = "socks5h://127.0.0.1:9050"
TIMEOUT = 10
MAX_THREADS = 50
# ======================

def extract_clean_onion(raw):
    raw = raw.strip().lower()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        hostname = urlparse(raw).hostname
    else:
        hostname = raw.split("/")[0]
    return hostname if hostname and hostname.endswith(".onion") else None

def load_onions_from_txt(path):
    with open(path, "r") as f:
        lines = f.readlines()
    return list({extract_clean_onion(line) for line in lines if extract_clean_onion(line)})

def load_onions_from_csv(path):
    onions = set()
    with open(path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            for cell in row:
                url = extract_clean_onion(cell)
                if url:
                    onions.add(url)
    return list(onions)

def load_onions_from_sqlite(path, table, column):
    onions = set()
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT {column} FROM {table}")
    for row in cursor.fetchall():
        url = extract_clean_onion(row[0])
        if url:
            onions.add(url)
    conn.close()
    return list(onions)

def load_onion_urls():
    ext = os.path.splitext(INPUT_FILE)[1].lower()
    if ext == ".txt":
        return load_onions_from_txt(INPUT_FILE)
    elif ext == ".csv":
        return load_onions_from_csv(INPUT_FILE)
    elif ext == ".sqlite":
        return load_onions_from_sqlite(INPUT_FILE, SQLITE_TABLE, SQLITE_COLUMN)
    else:
        raise ValueError("Unsupported input format. Use .txt, .csv, or .sqlite")

def check_onion(url):
    full_url = f"http://{url}"
    proxies = {"http": TOR_PROXY, "https": TOR_PROXY}
    start = time.perf_counter()
    try:
        response = requests.get(full_url, proxies=proxies, timeout=TIMEOUT)
        duration = round(time.perf_counter() - start, 2)
        if response.status_code == 200:
            return {"url": url, "status": "ONLINE", "response_time": duration}
        else:
            return {"url": url, "status": f"ERROR {response.status_code}", "response_time": duration}
    except Exception:
        duration = round(time.perf_counter() - start, 2)
        return {"url": url, "status": "OFFLINE", "response_time": duration}

def save_csv(results, filename="results.csv"):
    with open(filename, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["url", "status", "response_time"])
        writer.writeheader()
        writer.writerows(results)

def save_json(results, filename="results.json"):
    with open(filename, "w") as file:
        json.dump(results, file, indent=4)

def main():
    print("📥 Loading onion URLs...")
    onion_urls = load_onion_urls()
    print(f"🔍 Loaded {len(onion_urls)} unique .onion addresses\n")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(check_onion, url): url for url in onion_urls}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"[{result['status']:<12}] {result['url']} ⏱️ {result['response_time']}s")

    avg_time = round(sum(r["response_time"] for r in results) / len(results), 2)
    print(f"\n📊 Average response time: {avg_time} seconds")

    save_csv(results)
    save_json(results)

    print("\n✅ Done! Results saved to:")
    print("📁 results.csv")
    print("📁 results.json")

if __name__ == "__main__":
    main()
