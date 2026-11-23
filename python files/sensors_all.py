import smbus2
import bme280
import time

bus_light = smbus2.SMBus(1)
bus_bme = smbus2.SMBus(3)

LIGHT_ADDR = 0x23
BME_ADDR = 0x76

calibration_params = bme280.load_calibration_params(bus_bme, BME_ADDR)

def read_light():
    data = bus_light.read_i2c_block_data(LIGHT_ADDR, 0x10, 2)
    lux = ((data[0] << 8) | data[1]) / 1.2
    return lux

print("Метеостанцію запущено (Ctrl+C для виходу)...")
try:
    while True:
        lux = read_light()
        weather = bme280.sample(bus_bme, BME_ADDR, calibration_params)
        pressure_mmhg = weather.pressure * 0.750062

        print(
            f"Темп: {weather.temperature:.1f} °C | "
            f"Вологість: {weather.humidity:.1f} % | "
            f"Тиск: {weather.pressure:.1f} гПа ({pressure_mmhg:.0f} мм) | "
            f"Освітлення: {lux:.1f} лк"
        )
        time.sleep(2)
except KeyboardInterrupt:
    print("\nЗбір даних зупинено.")