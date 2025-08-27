import os
os.environ["BLINKA_FT232H"] = "1"
import struct
import time
import threading
import matplotlib.pyplot as plt
from collections import deque
import board
import busio

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
# Main program (plot only)
############################################
if __name__ == "__main__":
    if not init_ina231():
        exit(1)

    # Start background INA231 data collection
    threading.Thread(target=data_collector_thread, daemon=True).start()

    # Setup live plot in MAIN thread
    plt.ion()
    fig = plt.figure(figsize=(10, 6))

    try:
        while running:
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

            # Exit if plot window is closed
            if not plt.fignum_exists(fig.number):
                running = False
                break

    except KeyboardInterrupt:
        running = False
        print("\nStopping...")
    finally:
        running = False
        plt.close('all')
        print("Program exited safely.")
