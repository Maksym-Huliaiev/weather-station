import smbus2
import time

DEVICE = 0x23 

# Режими вимірювання
POWER_DOWN = 0x00
POWER_ON = 0x01
RESET = 0x07
CONTINUOUS_HIGH_RES_MODE = 0x10

bus = smbus2.SMBus(1)

def read_light():
    # Читання даних з датчика
    data = bus.read_i2c_block_data(DEVICE, CONTINUOUS_HIGH_RES_MODE, 2)
    # Перерахунок в люкси
    return (data[1] + (256 * data[0])) / 1.2

print("Читання даних з датчика BH1750 (Ctrl+C для виходу)...")
try:
    while True:
        lux = read_light()
        print(f"Освітленість: {lux:.2f} lx")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nПрограму зупинено.")