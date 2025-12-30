#!/usr/bin/env python3
"""Простой скрипт для проверки подключения к Weaviate"""

import os
import sys
import requests
import time

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")

def check_weaviate():
    """Проверяет доступность Weaviate"""
    print(f"🔍 Проверка подключения к {WEAVIATE_URL}...")
    
    for i in range(30):
        try:
            response = requests.get(f"{WEAVIATE_URL}/v1/meta", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Weaviate доступен!")
                print(f"   Версия: {data.get('version', 'unknown')}")
                print(f"   Модули: {', '.join(data.get('modules', {}).keys())}")
                return True
        except requests.exceptions.RequestException as e:
            if i < 29:
                print(f"⏳ Попытка {i+1}/30... ({str(e)[:50]})")
                time.sleep(2)
            else:
                print(f"❌ Weaviate недоступен: {e}")
                return False
    
    return False

if __name__ == "__main__":
    if check_weaviate():
        sys.exit(0)
    else:
        sys.exit(1)
