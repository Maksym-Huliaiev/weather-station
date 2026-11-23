import smbus2
import bme280
import time

port = 1
address = 0x76
bus = smbus2.SMBus(port)

calibration_params = bme280.load_calibration_params(bus, address)

print("Читання даних з датчика BME280 (Ctrl+C для виходу)...")
try:
    while True:
        data = bme280.sample(bus, address, calibration_params)
        print(f"Температура: {data.temperature:.2f} °C | Тиск: {data.pressure:.2f} гПа | Вологість: {data.humidity:.2f} %")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nПрограму зупинено.")