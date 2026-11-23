import csv
import io
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime
import bme280
import smbus2
from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)
DB_PATH = "weather.db"

# Інтервал збереження в базу даних у секундах (60 = раз на хвилину)
SAVE_INTERVAL = 60

bus_light = smbus2.SMBus(1)
bus_bme = smbus2.SMBus(3)
LIGHT_ADDR = 0x23
BME_ADDR = 0x76
calibration_params = bme280.load_calibration_params(bus_bme, BME_ADDR)

latest_data = {
    "timestamp": "--:--:--",
    "temperature": 0.0,
    "humidity": 0.0,
    "pressure_hpa": 0.0,
    "pressure_mmhg": 0.0,
    "lux": 0.0,
}

# буфер у пам'яті для плавного графіка в режимі "Наживо"
live_history = deque(maxlen=40)


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                pressure_hpa REAL NOT NULL,
                pressure_mmhg REAL NOT NULL,
                lux REAL NOT NULL
            )
        """)


def read_sensors_smoothed():
    lux_vals, temp_vals, hum_vals, press_vals = [], [], [], []
    for _ in range(3):
        raw_light = bus_light.read_i2c_block_data(LIGHT_ADDR, 0x10, 2)
        lux_vals.append(((raw_light[0] << 8) | raw_light[1]) / 1.2)

        weather = bme280.sample(bus_bme, BME_ADDR, calibration_params)
        temp_vals.append(weather.temperature)
        hum_vals.append(weather.humidity)
        press_vals.append(weather.pressure)
        time.sleep(0.15)

    lux = round(sum(lux_vals) / len(lux_vals), 1)
    temp = round(sum(temp_vals) / len(temp_vals), 1)
    hum = round(sum(hum_vals) / len(hum_vals), 1)
    press_hpa = round(sum(press_vals) / len(press_vals), 1)
    press_mmhg = round(press_hpa * 0.750062, 1)

    return temp, hum, press_hpa, press_mmhg, lux


def save_to_db(record):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO measurements (timestamp, temperature, humidity, pressure_hpa, pressure_mmhg, lux)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record["timestamp"],
                record["temperature"],
                record["humidity"],
                record["pressure_hpa"],
                record["pressure_mmhg"],
                record["lux"],
            ),
        )


def background_collector():
    global latest_data
    last_saved_time = 0

    while True:
        try:
            temp, hum, press_hpa, press_mmhg, lux = read_sensors_smoothed()
            now_dt = datetime.now()
            now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

            record = {
                "timestamp": now_str,
                "temperature": temp,
                "humidity": hum,
                "pressure_hpa": press_hpa,
                "pressure_mmhg": press_mmhg,
                "lux": lux,
            }

            latest_data = record
            live_history.append(record)

            if time.time() - last_saved_time >= SAVE_INTERVAL:
                save_to_db(record)
                last_saved_time = time.time()

        except Exception as e:
            print(f"Помилка зчитування: {e}")

        time.sleep(3)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    selected_date = request.args.get("date", "live")

    if selected_date == "live":
        history = list(live_history)
    else:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM measurements WHERE timestamp LIKE ? ORDER BY id ASC",
                (f"{selected_date}%",),
            ).fetchall()
        history = [dict(row) for row in rows]

    # розрахунок статистики (мін/макс/середнє) для обраного набору даних
    stats = None
    if history:
        temps = [r["temperature"] for r in history]
        hums = [r["humidity"] for r in history]
        press = [r["pressure_mmhg"] for r in history]
        luxes = [r["lux"] for r in history]
        stats = {
            "count": len(history),
            "temp_min": min(temps),
            "temp_max": max(temps),
            "temp_avg": round(sum(temps) / len(temps), 1),
            "hum_min": min(hums),
            "hum_max": max(hums),
            "press_min": min(press),
            "press_max": max(press),
            "lux_max": max(luxes),
            "lux_avg": round(sum(luxes) / len(luxes), 1),
        }

    return jsonify({"current": latest_data, "history": history, "stats": stats})


@app.route("/export")
def export_csv():
    selected_date = request.args.get("date", "all")
    with sqlite3.connect(DB_PATH) as conn:
        if selected_date != "all" and selected_date != "live":
            rows = conn.execute(
                "SELECT timestamp, temperature, humidity, pressure_hpa, pressure_mmhg, lux FROM measurements WHERE timestamp LIKE ? ORDER BY id ASC",
                (f"{selected_date}%",),
            ).fetchall()
            filename = f"weather_{selected_date}.csv"
        else:
            rows = conn.execute(
                "SELECT timestamp, temperature, humidity, pressure_hpa, pressure_mmhg, lux FROM measurements ORDER BY id ASC"
            ).fetchall()
            filename = "weather_all.csv"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Дата і час", "Температура (°C)", "Вологість (%)", "Тиск (гПа)", "Тиск (мм рт. ст.)", "Освітленість (лк)"])
    writer.writerows(rows)

    return Response(
        output.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


if __name__ == "__main__":
    init_db()
    collector_thread = threading.Thread(target=background_collector, daemon=True)
    collector_thread.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
