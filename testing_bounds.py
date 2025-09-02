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
    
    print("Detecting servo bounds from current position...")
    
    # Read current angle (servo stays wherever it is)
    current_angle = servo_motor.angle
    print(f"Starting from current position: {current_angle}°")
    
    # First, move clockwise from current position to find max bound
    servo_max_bound = 180
    for angle in range(int(current_angle), 181):
        servo_motor.angle = angle
        time.sleep(0.1)
        current = read_current()
        if current > current_threshold:
            servo_max_bound = angle - 1
            print(f"Clockwise limit found at {servo_max_bound}°")
            break
    
    # Then move counterclockwise from current position to find min bound
    servo_min_bound = 0
    for angle in range(int(current_angle), -1, -1):
        servo_motor.angle = angle
        time.sleep(0.1)
        current = read_current()
        if current > current_threshold:
            servo_min_bound = angle + 1
            print(f"Counterclockwise limit found at {servo_min_bound}°")
            break
    
    # Move to center position between min and max bounds
    center_angle = (servo_min_bound + servo_max_bound) / 2
    servo_motor.angle = center_angle
    time.sleep(0.5)  # Allow time to reach center position
    
    bounds_detected = True
    print(f"Safe operating range: {servo_min_bound}° to {servo_max_bound}°")
    print(f"Servo moved to center position: {center_angle:.1f}°")

# ============================================================================
# MAIN PROGRAM
# ============================================================================
if __name__ == "__main__":
    if not init_ina231():
        exit(1)
    
    # Start data collection and live plotting
    threading.Thread(target=data_collector, daemon=True).start()
    
    # Setup live plotting
    plt.ion()
    fig = plt.figure(figsize=(10, 6))
    
    # Start bounds detection in background
    threading.Thread(target=detect_bounds, daemon=True).start()
    
    try:
        while running:
            if current_data:
                plt.clf()
                plt.plot(list(time_data), list(current_data), 'b-')
                plt.axhline(y=current_threshold, color='r', linestyle='--', label=f'{current_threshold}mA Threshold')
                plt.xlabel('Time (s)')
                plt.ylabel('Current (mA)')
                
                if bounds_detected:
                    plt.title(f'Servo Limits: {servo_min_bound}° to {servo_max_bound}° | Center: {(servo_min_bound + servo_max_bound)/2:.1f}° | Current: {current_data[-1]:.2f}mA')
                else:
                    plt.title(f'Detecting Limits... | Current: {current_data[-1]:.2f}mA')
                
                plt.grid(True, alpha=0.3)
                plt.legend()
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
        print("Program exited safely.")