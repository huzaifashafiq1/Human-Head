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

# Create servo objects for channels 0-5
servos = []
for i in range(6):
    servos.append(servo.Servo(pca.channels[i], min_pulse=500, max_pulse=2500))

# Store bounds for each servo
servo_bounds = {i: {"min": 0, "max": 180, "center": 90} for i in range(6)}

# ============================================================================
# CONFIGURATION
# ============================================================================
current_threshold = 7.0  # mA - default threshold
servo2_threshold = 8.0   # mA - special threshold for servo 2
servo3_threshold = 10.0   # mA - special threshold for servo 3
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
def detect_bounds_for_servo(servo_num):
    servo_motor = servos[servo_num]
    
    print(f"\n=== Detecting bounds for Servo {servo_num} ===")
    
    # Use appropriate current threshold for each servo
    if servo_num == 2:
        threshold = servo2_threshold
        print(f"Using special current threshold for servo 2: {threshold}mA")
    elif servo_num == 3:
        threshold = servo3_threshold
        print(f"Using special current threshold for servo 3: {threshold}mA")
    else:
        threshold = current_threshold
    
    # Read current angle (servo stays wherever it is)
    current_angle = servo_motor.angle
    print(f"Starting from current position: {current_angle}°")
    
    # Movement parameters
    step_delay = 0.005
    angle_increment = 1
    
    # First, move clockwise from current position to find max bound
    max_bound = 180
    angle = float(current_angle)
    while angle <= 180:
        servo_motor.angle = angle
        time.sleep(step_delay)
        current = read_current()  # Use direct current reading
        if current > threshold:
            print(f"Clockwise limit found at {angle:.1f}° (current: {current:.2f}mA)")
            max_bound = angle -3
            break
        angle += angle_increment
    
    min_bound = 0
    angle = float(max_bound)
    loop_count = 0

    while angle >= 0:
        servo_motor.angle = angle
        time.sleep(step_delay)
        current = read_current()
        loop_count += 1
    
        # Skip current checking for first 10 loops
        if loop_count <= 20:
            angle -= angle_increment
            continue
    
    # Check condition after 10 loops
        if current > threshold:
            # Instantly bounce back from the limit
        
            print(f"Counterclockwise limit found at {angle:.1f}° (current: {current:.2f}mA)")
            min_bound = angle +3
            break
        angle -= angle_increment
   
    # Calculate center position for all servos
    center_position = (min_bound + max_bound) / 2
    
    # Store the bounds for this servo
    servo_bounds[servo_num]["min"] = min_bound
    servo_bounds[servo_num]["max"] = max_bound
    servo_bounds[servo_num]["center"] = center_position
    
    # Special handling for specific servos - set temporary final position
    if servo_num == 0:
        # Servo 0 stays at maximum temporarily
        final_position = max_bound
        print(f"Servo 0 temporarily at maximum position: {final_position:.1f}°")
    elif servo_num == 4:
        # Servo 4 stays at minimum temporarily
        final_position = min_bound
        print(f"Servo 4 temporarily at minimum position: {final_position:.1f}°")
    else:
        # All other servos stop at center immediately
        final_position = center_position
        print(f"Servo {servo_num} moving to center position: {final_position:.1f}°")
    
    # Move to temporary final position
    servo_motor.angle = final_position
    
    print(f"Servo {servo_num} safe operating range: {min_bound:.1f}° to {max_bound:.1f}°")
    print(f"Servo {servo_num} temporary position: {final_position:.1f}°")
    
    return min_bound, max_bound, center_position

def move_servo_to_center(servo_num):
    """Move a servo to its center position"""
    center_position = servo_bounds[servo_num]["center"]
    servos[servo_num].angle = center_position
    print(f"Moved servo {servo_num} to center position: {center_position:.1f}°")
    time.sleep(0.2)

def detect_all_bounds():
    global bounds_detected
    
    print("Starting sequential bounds detection for servos 0,1,4,5,2,3...")
    
    # Define the custom detection order: 0,1,4,5,2,3
    servo_order = [0, 1, 4, 5, 3, 2]
    
    # Detect bounds for each servo in the custom order
    for i, servo_num in enumerate(servo_order):
        min_bound, max_bound, center_position = detect_bounds_for_servo(servo_num)
        
        # Special handling: Move servo 0 to center after servo 1 completes
        if servo_num == 1:  # After servo 1 completes
            print("\nMoving servo 0 to its center position...")
            move_servo_to_center(0)
        
        # Special handling: Move servo 4 to center after servo 5 completes  
        if servo_num == 5:  # After servo 5 completes
            print("\nMoving servo 4 to its center position...")
            move_servo_to_center(4)
        
        # Brief pause between servos (except after the last one)
        if i < len(servo_order) - 1:
            print(f"\nMoving to next servo (Servo {servo_order[i+1]}) in 1 second...")
            time.sleep(1)
    
    bounds_detected = True
    print("\n=== All servo bounds detection complete ===")
    # Print results in numerical order for clarity
    for servo_num in range(6):
        bounds = servo_bounds[servo_num]
        print(f"Servo {servo_num}: {bounds['min']:.1f}° to {bounds['max']:.1f}° (Center: {bounds['center']:.1f}°)")

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
    threading.Thread(target=detect_all_bounds, daemon=True).start()
    
    try:
        while running:
            if current_data:
                plt.clf()
                plt.plot(list(time_data), list(current_data), 'b-')
                plt.axhline(y=current_threshold, color='r', linestyle='--', label=f'Default Threshold ({current_threshold}mA)')
                plt.axhline(y=servo2_threshold, color='g', linestyle='--', label=f'Servo 2 Threshold ({servo2_threshold}mA)')
                plt.axhline(y=servo3_threshold, color='orange', linestyle='--', label=f'Servo 3 Threshold ({servo3_threshold}mA)')
                plt.xlabel('Time (s)')
                plt.ylabel('Current (mA)')
                
                if bounds_detected:
                    title = "All Servo Bounds Detected | "
                    for i in range(6):
                        bounds = servo_bounds[i]
                        title += f"S{i}:{bounds['min']:.0f}-{bounds['max']:.0f}° "
                    title += f"| Current: {current_data[-1]:.2f}mA"
                    plt.title(title)
                else:
                    plt.title(f'Detecting Limits for All Servos... | Current: {current_data[-1]:.2f}mA')
                
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
        print("\nFinal Servo Bounds and Positions:")
        for servo_num in range(6):
            bounds = servo_bounds[servo_num]
            print(f"Servo {servo_num}: {bounds['min']:.1f}° to {bounds['max']:.1f}° (Center: {bounds['center']:.1f}°)")