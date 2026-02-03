import time
import os
import csv
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

load_dotenv()

# --- CONFIGURATION ---
PRODUCTS = {
    "CC02": "https://www.toylaxy.com/en/product/1227227/product-1227227?category_id=125777",
    # "SL02": "https://www.toylaxy.com/en/product/1273208/product-1273208?category_id=137697",
    "BT09": "https://www.toylaxy.com/en/product/1246962/product-1246962?category_id=137697",
    "BT08": "https://www.toylaxy.com/en/product/1227221/product-1227221?category_id=125777"
}

STATE_FILE = "state.csv"
NOTIFICATION_COOLDOWN_MINUTES = 60

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
LINE_GROUP_ID = os.getenv("LINE_GROUP_ID")
HEADLESS = os.getenv("GITHUB_ACTIONS") == "true" or True 

def load_state():
    """Reads the CSV and returns a dict {product_name: timestamp_string}"""
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, mode='r') as f:
            reader = csv.reader(f)
            state = {rows[0]: rows[1] for rows in reader if rows}
    return state

def save_state(state):
    """Writes the current notification state to the CSV"""
    with open(STATE_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        for name, ts in state.items():
            writer.writerow([name, ts])

def send_line_message(message):
    if not LINE_ACCESS_TOKEN or not LINE_GROUP_ID:
        print("Missing LINE Credentials (Token or Group ID)")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    payload = {
        # "to": LINE_GROUP_ID, 
        "to": LINE_USER_ID, 
        "messages": [{"type": "text", "text": message}]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"Notification pushed to Group: {LINE_GROUP_ID[:10]}...")
    else:
        print(f"Failed to push message: {response.text}")

def get_driver(headless=True):
    options = Options()
    if headless: options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def check_all_products():
    state = load_state()
    driver = get_driver(headless=HEADLESS)
    now = datetime.now()
    
    try:
        for name, url in PRODUCTS.items():
            print(f"Checking {name}...")
            driver.get(url)
            time.sleep(5) 
            
            buttons = driver.find_elements(By.CLASS_NAME, "btn-block")
            if buttons:
                status_text = buttons[0].text.strip().lower()
                is_in_stock = "notify me" not in status_text and "out of stock" not in status_text
                
                if is_in_stock:
                    # Logic: Check if we notified recently
                    last_notified_str = state.get(name)
                    should_notify = True
                    
                    if last_notified_str:
                        last_notified_dt = datetime.fromisoformat(last_notified_str)
                        if now - last_notified_dt < timedelta(minutes=NOTIFICATION_COOLDOWN_MINUTES):
                            print(f"[{name}] Available, but notified recently. Skipping.")
                            should_notify = False
                    
                    if should_notify:
                        msg = f"✅ {name} AVAILABLE!\nStatus: {status_text.upper()}\n{url}"
                        send_line_message(msg)
                        state[name] = now.isoformat() # Update timestamp
                        print(f"[{name}] Notification sent!")
                else:
                    print(f"[{name}] Still: {status_text}")
        
        save_state(state) # Sync state back to CSV
    finally:
        driver.quit()

if __name__ == "__main__":
    # Run 5 times with a 2-minute gap within one 11-minute GitHub cycle
    for i in range(5):
        print(f"--- Sub-run {i+1} of 5 ---")
        check_all_products()
        if i < 4:  # Don't sleep after the last run
            print("Sleeping for 120 seconds...")
            time.sleep(120)