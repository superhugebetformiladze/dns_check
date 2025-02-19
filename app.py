import socket
import asyncio
import json
import os
from urllib.parse import urlparse
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from datetime import datetime
import pytz

SITES = ["https://ya.ru", "https://www.dns-shop.ru"]
clients = set()
interval = 2  # Начальный интервал в секундах
monitor_task = None  # Хранение задачи мониторинга

def check_dns(site):
    tz = pytz.timezone("Europe/Moscow")
    time = datetime.now(tz).strftime("%d/%m/%y %I:%M:%S")
    try:
        hostname = urlparse(site).hostname
        ip = socket.gethostbyname(hostname)
        return {"site": site, "status": "working", "info": "✅ DNS работает", "ip": ip, "time": time}
    except socket.gaierror:
        return {"site": site, "status": "unworking", "info": "❌ DNS не работает", "time": time}

async def monitor_sites():
    """Фоновая задача мониторинга с динамическим обновлением интервала"""
    global interval
    while True:
        results = [check_dns(site) for site in SITES]
        data = json.dumps(results, ensure_ascii=False)
        
        for client in clients:
            await client.send_text(data)

        await asyncio.sleep(interval)

async def restart_monitoring():
    """Останавливает текущий мониторинг и запускает новый с обновленным интервалом"""
    global monitor_task
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task  # Ждём отмены задачи
        except asyncio.CancelledError:
            pass  # Ожидаем исключение, если таска отменена
    monitor_task = asyncio.create_task(monitor_sites())

@asynccontextmanager
async def lifespan(app: FastAPI):
    global monitor_task
    monitor_task = asyncio.create_task(monitor_sites())
    yield
    monitor_task.cancel()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get():
    return HTMLResponse(open("templates/index.html", encoding="utf-8").read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global interval
    await websocket.accept()
    clients.add(websocket)

    results = [check_dns(site) for site in SITES]
    await websocket.send_text(json.dumps(results, ensure_ascii=False))

    # Отправляем текущий интервал при подключении
    await websocket.send_text(json.dumps({"type": "interval_update", "interval": interval}))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "get_interval":
                await websocket.send_text(json.dumps({"type": "interval_update", "interval": interval}))

            elif message.get("type") == "update_interval":
                new_interval = max(1, message.get("interval"))  # Минимальный интервал — 1 сек
                if new_interval != interval:
                    interval = new_interval
                    await restart_monitoring()  # Перезапускаем мониторинг

                    # Отправляем новый интервал всем клиентам
                    for client in clients:
                        await client.send_text(json.dumps({"type": "interval_update", "interval": interval}))
    except:
        clients.remove(websocket)
