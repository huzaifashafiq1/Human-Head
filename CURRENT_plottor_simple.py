import os
os.environ["BLINKA_FT232H"] = "1"

import board
import busio
import struct
import time
import threading
import matplotlib.pyplot as plt
import numpy as np
from collections import deque

# INA231 Configuration
INA231_ADDRESS = 0x40
INA231_CONFIG_REG = 0x00
INA231_CURRENT = 0x04
INA231_CALIBRATION = 0x05
INA231_CONFIG_DEFAULT = 0x4527
INA231_CALIBRATION_VAL = 0x0A00

# Create I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Data storage
current_data = deque(maxlen=1000)  # Store last 1000 readings
time_data = deque(maxlen=1000)
start_time = time.time()
running = True

def write_ina231(reg, value):
    """Write to INA231 register"""
    try:
        data = struct.pack('>BH', reg, value)
        i2c.writeto(INA231_ADDRESS, data)
        return True
    except Exception as e:
        print(f"Write error: {e}")
        return False

def read_ina231(reg):
    """Read from INA231 register"""
    try:
        i2c.writeto(INA231_ADDRESS, bytes([reg]))
        result = bytearray(2)
        i2c.readfrom_into(INA231_ADDRESS, result)
        return struct.unpack('>H', result)[0]
    except Exception as e:
        print(f"Read error: {e}")
        return 0

def init_ina231():
    """Initialize INA231"""
    print("Initializing INA231...")
    
    # Configure INA231
    if not write_ina231(INA231_CONFIG_REG, INA231_CONFIG_DEFAULT):
        return False
    if not write_ina231(INA231_CALIBRATION, INA231_CALIBRATION_VAL):
        return False
    
    time.sleep(0.1)
    print("✓ INA231 ready!")
    return True

def read_current():
    """Read current in mA"""
    raw = read_ina231(INA231_CURRENT)
    if raw > 32767:  # Handle signed 16-bit
        raw -= 65536
    return raw * 0.001  # Convert to mA

def data_thread():
    """Continuously read current data"""
    global running
    
    while running:
        try:
            current_mA = read_current()
            elapsed_time = time.time() - start_time
            
            current_data.append(current_mA)
            time_data.append(elapsed_time)
            
            time.sleep(0.05)  # 20Hz sampling
            
        except Exception as e:
            print(f"Data error: {e}")
            time.sleep(0.1)

def update_plot():
    """Update the live plot"""
    if len(current_data) == 0:
        return
    
    # Clear and plot new data
    plt.clf()
    
    times = list(time_data)
    currents = list(current_data)
    
    plt.plot(times, currents, 'b-', linewidth=2, label='Current (mA)')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Current (mA)')
    plt.title(f'Live Current Monitor - Latest: {currents[-1]:.1f} mA')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    # Show last 30 seconds
    if len(times) > 0:
        plt.xlim(max(0, times[-1] - 30), times[-1] + 1)
    
    plt.tight_layout()
    plt.draw()

def main():
    """Main function"""
    global running
    
    print("🚀 Simple INA231 Current Monitor")
    print("Press Ctrl+C to exit")
    
    # Initialize INA231
    if not init_ina231():
        print("❌ Failed to initialize INA231!")
        return
    
    # Start data collection thread
    data_collector = threading.Thread(target=data_thread, daemon=True)
    data_collector.start()
    
    # Setup plot
    plt.ion()  # Interactive mode
    fig = plt.figure(figsize=(10, 6))
    
    print("✓ Starting live plot...")
    print("💡 Current readings should appear in a new window")
    
    try:
        # Main plotting loop
        while running:
            update_plot()
            plt.pause(0.1)  # Update every 100ms
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
    except Exception as e:
        print(f"❌ Plot error: {e}")
    finally:
        running = False
        plt.close('all')
        print("✅ Done!")
if __name__ == "__main__":
    main()