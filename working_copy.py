import os
os.environ["BLINKA_FT232H"] = "1"
import board
import busio
import struct
import time
import threading
import matplotlib.pyplot as plt
from collections import deque
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

# ============================================================================
# HARDWARE INITIALIZATION
# ============================================================================
i2c = busio.I2C(board.SCL, board.SDA)

# INA231 Current Sensor
INA231_ADDRESS = 0x40
current_data = deque(maxlen=1000)
time_data = deque(maxlen=1000)
start_time = time.time()

# Servo Control
pca = PCA9685(i2c, address=0x42)
pca.frequency = 50
servo_motor = servo.Servo(pca.channels[10], min_pulse=500, max_pulse=2500)

# ============================================================================
# CONFIGURATION
# ============================================================================
current_threshold = 4.0  # mA
servo_min_bound = 0
servo_max_bound = 180
bounds_detected = False
running = True

# ============================================================================
# INA231 FUNCTIONS
# ============================================================================
def init_ina231():
    try:
        i2c.writeto(INA231_ADDRESS, struct.pack('>BH', 0x00, 0x4527))  # Config
        i2c.writeto(INA231_ADDRESS, struct.pack('>BH', 0x05, 0x0A00))  # Calibration
        time.sleep(0.1)
        print("✓ INA231 ready!")
        return True
    except Exception as e:
        print(f"INA231 init error: {e}")
        return False

def read_current():
    try:
        i2c.writeto(INA231_ADDRESS, bytes([0x04]))
        result = bytearray(2)
        i2c.readfrom_into(INA231_ADDRESS, result)
        raw = struct.unpack('>H', result)[0]
        return (raw - 65536 if raw > 32767 else raw) * 0.001
    except:
        return 0

def data_collector():
    global running
    while running:
        current_data.append(read_current())
        time_data.append(time.time() - start_time)
        time.sleep(0.05)

# ============================================================================
# SERVO BOUNDS DETECTION
# ============================================================================
def detect_bounds():
    global servo_min_bound, servo_max_bound, bounds_detected
    
    print("Detecting servo bounds...")
    servo_motor.angle = 90
    time.sleep(1)
    
    # Find max bound (clockwise)
    for angle in range(90, 181):
        servo_motor.angle = angle
        time.sleep(0.1)
        if read_current() > current_threshold:
            servo_max_bound = angle - 1
            break
    
    # Find min bound (counterclockwise)
    servo_motor.angle = 90
    time.sleep(1)
    for angle in range(90, -1, -1):
        servo_motor.angle = angle
        time.sleep(0.1)
        if read_current() > current_threshold:
            servo_min_bound = angle + 1
            break
    
    center = (servo_min_bound + servo_max_bound) / 2
    servo_motor.angle = center
    bounds_detected = True
    print(f"Bounds: {servo_min_bound}°-{servo_max_bound}°, Centered at {center:.1f}°")

# ============================================================================
# MAIN PROGRAM
# ============================================================================
if __name__ == "__main__":
    if not init_ina231():
        exit(1)
    
    # Start data collection and live plotting
    threading.Thread(target=data_collector, daemon=True).start()
    servo_motor.angle = 90
    
    # Setup live plotting first
    plt.ion()
    fig = plt.figure(figsize=(10, 6))
    
    # Start bounds detection in background
    threading.Thread(target=detect_bounds, daemon=True).start()
    
    try:
        while running:
            if current_data:
                plt.clf()
                plt.plot(list(time_data), list(current_data), 'b-')
                plt.axhline(y=current_threshold, color='r', linestyle='--')
                plt.xlabel('Time (s)')
                plt.ylabel('Current (mA)')
                plt.title(f'Live Current Monitor | Current: {current_data[-1]:.2f}mA')
                plt.grid(True, alpha=0.3)
                if time_data:
                    plt.xlim(max(0, time_data[-1]-30), time_data[-1]+1)
                plt.tight_layout()
                plt.draw()
            plt.pause(0.05)
            
            if not plt.fignum_exists(fig.number):
                break
                
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        running = False
        plt.close('all')
        servo_motor.angle = 90
        print("Program exited safely.")