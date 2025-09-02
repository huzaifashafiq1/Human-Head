import os
os.environ["BLINKA_FT232H"] = "1"
import sys
import select
import board
import busio
import struct
import time
import threading
import matplotlib.pyplot as plt
from collections import deque
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

############################################
# Shared I2C bus
############################################
i2c = busio.I2C(board.SCL, board.SDA)

############################################
# INA231 setup
############################################
INA231_ADDRESS = 0x40
INA231_CONFIG_REG = 0x00
INA231_CURRENT = 0x04
INA231_CALIBRATION = 0x05
INA231_CONFIG_DEFAULT = 0x4527
INA231_CALIBRATION_VAL = 0x0A00

current_data = deque(maxlen=1000)
time_data = deque(maxlen=1000)
running = True
start_time = time.time()

def write_ina231(reg, value):
    try:
        data = struct.pack('>BH', reg, value)
        i2c.writeto(INA231_ADDRESS, data)
        return True
    except Exception as e:
        print(f"Write error: {e}")
        return False

def read_ina231(reg):
    try:
        i2c.writeto(INA231_ADDRESS, bytes([reg]))
        result = bytearray(2)
        i2c.readfrom_into(INA231_ADDRESS, result)
        return struct.unpack('>H', result)[0]
    except Exception as e:
        print(f"Read error: {e}")
        return 0

def init_ina231():
    print("Initializing INA231...")
    if not write_ina231(INA231_CONFIG_REG, INA231_CONFIG_DEFAULT):
        return False
    if not write_ina231(INA231_CALIBRATION, INA231_CALIBRATION_VAL):
        return False
    time.sleep(0.1)
    print("✓ INA231 ready!")
    return True

def read_current():
    raw = read_ina231(INA231_CURRENT)
    if raw > 32767:
        raw -= 65536
    return raw * 0.001  # mA

def data_collector_thread():
    global running
    while running:
        try:
            current_mA = read_current()
            elapsed_time = time.time() - start_time
            current_data.append(current_mA)
            time_data.append(elapsed_time)
            time.sleep(0.05)
        except Exception as e:
            print(f"Data read error: {e}")
            time.sleep(0.1)

############################################
# Servo setup
############################################
pca = PCA9685(i2c, address=0x42)
pca.frequency = 50

servos = {}
available_channels = [8, 9, 10, 11]
for ch in available_channels:
    servos[ch] = servo.Servo(pca.channels[ch], min_pulse=500, max_pulse=2500)

def center_all_servos():
    for ch in available_channels:
        try:
            servos[ch].angle = 90
        except:
            pass

def sweep_servo(channel, speed=0.1):
    if channel not in servos:
        print("Invalid channel")
        return
    try:
        for angle in range(0, 60, 5):
            servos[channel].angle = angle
            time.sleep(speed)
        for angle in range(59, -1, -5):
            servos[channel].angle = angle
            time.sleep(speed)
    except Exception as e:
        print(f"Error sweeping channel {channel}: {e}")

############################################
# Main program (input + plotting in main thread)
############################################
if __name__ == "__main__":
    if not init_ina231():
        exit(1)

    # Start background INA231 data collection
    threading.Thread(target=data_collector_thread, daemon=True).start()

    # Center servos at start
    center_all_servos()

    # Start sweeping only servo 10 in background
    threading.Thread(target=sweep_servo, args=(10,), daemon=True).start()

    # Setup live plot in MAIN thread
    plt.ion()
    fig = plt.figure(figsize=(10, 6))

    try:
        while running:
            # --- Update plot ---
            if current_data:
                plt.clf()
                plt.plot(list(time_data), list(current_data), 'b-', label='Current (mA)')
                plt.xlabel('Time (s)')
                plt.ylabel('Current (mA)')
                plt.title(f'Live Current - Latest: {current_data[-1]:.2f} mA')
                plt.grid(True, alpha=0.3)
                plt.legend()
                if time_data:
                    plt.xlim(max(0, time_data[-1]-30), time_data[-1]+1)
                plt.tight_layout()
                plt.draw()
            plt.pause(0.05)

            # --- Exit if plot is closed ---
            if not plt.fignum_exists(fig.number):
                running = False
                break

    except KeyboardInterrupt:
        running = False
        print("\nStopping...")
    finally:
        running = False
        plt.close('all')
        center_all_servos()
        print("Program exited safely.")
