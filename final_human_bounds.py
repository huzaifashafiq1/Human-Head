import os
os.environ["BLINKA_FT232H"] = "1"
import board
import busio
import struct
import time
import threading
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo
import random

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
command_in_progress = False
human_eyes_active = False

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
            max_bound = angle -5
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
            min_bound = angle +5
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
    global bounds_detected, command_in_progress
    command_in_progress = True
    
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
    
    command_in_progress = False

# ============================================================================
# EYE MOVEMENT FUNCTIONS
# ============================================================================
def move_servo_safe(servo_num, angle):
    """Move a servo to a position, ensuring it stays within bounds"""
    min_bound = servo_bounds[servo_num]["min"]
    max_bound = servo_bounds[servo_num]["max"]
    
    # Constrain angle to safe range
    constrained_angle = max(min_bound, min(max_bound, angle))
    
    servos[servo_num].angle = constrained_angle
    return constrained_angle

def move_servo_thread(servo_num, angle):
    """Thread function to move a single servo"""
    min_bound = servo_bounds[servo_num]["min"]
    max_bound = servo_bounds[servo_num]["max"]
    constrained_angle = max(min_bound, min(max_bound, angle))
    servos[servo_num].angle = constrained_angle

def move_multiple_servos_simultaneously(servo_angle_pairs):
    """Move multiple servos simultaneously using threads"""
    threads = []
    
    for servo_num, angle in servo_angle_pairs:
        thread = threading.Thread(target=move_servo_thread, args=(servo_num, angle))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete (with a short timeout)
    for thread in threads:
        thread.join(timeout=0.1)  # 100ms timeout

def eyes_neutral():
    """Eyes open and looking straight (center position for all servos)"""
    print("Setting eyes to neutral position (open and looking straight)...")
    
    # Move all servos to their center positions simultaneously using threads
    servo_angle_pairs = []
    for servo_num in range(6):
        servo_angle_pairs.append((servo_num, servo_bounds[servo_num]["center"]))
    
    move_multiple_servos_simultaneously(servo_angle_pairs)

def eyes_blink():
    """Make the eyes blink simultaneously"""
    global command_in_progress
    command_in_progress = True
    
    if not bounds_detected:
        print("Error: Please run bounds detection first!")
        command_in_progress = False
        return
    
    print("Blinking eyes simultaneously...")
    
    # Close eyelids simultaneously using threads
    move_multiple_servos_simultaneously([
        (0, servo_bounds[0]["max"]),  # Top right eyelid closed
        (1, servo_bounds[1]["min"]),  # Bottom right eyelid closed
        (4, servo_bounds[4]["min"]),  # Top left eyelid closed
        (5, servo_bounds[5]["max"])   # Bottom left eyelid closed
    ])
    
    # Non-blocking delay for closed position
    blink_start = time.time()
    while time.time() - blink_start < 0.3 and running:
        time.sleep(0.01)
    
    # Open eyelids simultaneously using threads
    eyes_neutral()
    
    command_in_progress = False

def eyes_look_up():
    """Make eyes look up"""
    global command_in_progress
    command_in_progress = True
    
    if not bounds_detected:
        print("Error: Please run bounds detection first!")
        command_in_progress = False
        return
    
    print("Looking up...")
    # Servo 2 clockwise (max) makes eyes look up
    move_servo_safe(2, servo_bounds[2]["max"])
    
    # Non-blocking delay
    look_start = time.time()
    while time.time() - look_start < 1.0 and running:
        time.sleep(0.01)
    
    eyes_neutral()
    command_in_progress = False

def eyes_look_down():
    """Make eyes look down"""
    global command_in_progress
    command_in_progress = True
    
    if not bounds_detected:
        print("Error: Please run bounds detection first!")
        command_in_progress = False
        return
    
    print("Looking down...")
    # Servo 2 counterclockwise (min) makes eyes look down
    move_servo_safe(2, servo_bounds[2]["min"])
    
    # Non-blocking delay
    look_start = time.time()
    while time.time() - look_start < 1.0 and running:
        time.sleep(0.01)
    
    eyes_neutral()
    command_in_progress = False

def eyes_look_left():
    """Make eyes look left"""
    global command_in_progress
    command_in_progress = True
    
    if not bounds_detected:
        print("Error: Please run bounds detection first!")
        command_in_progress = False
        return
    
    print("Looking left...")
    # Servo 3 clockwise (max) makes eyes look left
    move_servo_safe(3, servo_bounds[3]["max"])
    
    # Non-blocking delay
    look_start = time.time()
    while time.time() - look_start < 1.0 and running:
        time.sleep(0.01)
    
    eyes_neutral()
    command_in_progress = False

def eyes_look_right():
    """Make eyes look right"""
    global command_in_progress
    command_in_progress = True
    
    if not bounds_detected:
        print("Error: Please run bounds detection first!")
        command_in_progress = False
        return
    
    print("Looking right...")
    # Servo 3 counterclockwise (min) makes eyes look right
    move_servo_safe(3, servo_bounds[3]["min"])
    
    # Non-blocking delay
    look_start = time.time()
    while time.time() - look_start < 1.0 and running:
        time.sleep(0.01)
    
    eyes_neutral()
    command_in_progress = False

# ============================================================================
# HUMAN EYES FUNCTIONALITY
# ============================================================================
def human_eyes():
    """Simulate natural human eye movements"""
    global human_eyes_active, running
    
    if not bounds_detected:
        print("Error: Please run bounds detection first!")
        return
    
    human_eyes_active = True
    print("Starting human-like eye movements. Press Ctrl+C to stop.")
    
    # Initialize eye state
    last_blink_time = time.time()
    last_gaze_change = time.time()
    current_gaze = (servo_bounds[2]["center"], servo_bounds[3]["center"])  # (vertical, horizontal)
    
    try:
        while human_eyes_active and running:
            current_time = time.time()
            
            # Random blinking (average 15-20 times per minute)
            if current_time - last_blink_time > random.uniform(2.0, 5.0):
                # Decide if it's a single or double blink (10% chance of double blink)
                if random.random() < 0.1:
                    # Double blink
                    eyes_blink()
                    time.sleep(0.1)
                    eyes_blink()
                else:
                    # Single blink
                    eyes_blink()
                
                last_blink_time = current_time
            
            # Random gaze changes (average every 3-8 seconds)
            if current_time - last_gaze_change > random.uniform(3.0, 8.0):
                # Calculate new gaze position (within 70% of bounds)
                v_min, v_max = servo_bounds[2]["min"], servo_bounds[2]["max"]
                h_min, h_max = servo_bounds[3]["min"], servo_bounds[3]["max"]
                
                v_range = v_max - v_min
                h_range = h_max - h_min
                
                new_v = v_min + 0.15 * v_range + random.random() * 0.7 * v_range
                new_h = h_min + 0.15 * h_range + random.random() * 0.7 * h_range
                
                # Smoothly move to new position
                steps = 20
                for i in range(steps):
                    if not human_eyes_active or not running:
                        break
                    
                    # Calculate intermediate position
                    v_pos = current_gaze[0] + (new_v - current_gaze[0]) * (i+1) / steps
                    h_pos = current_gaze[1] + (new_h - current_gaze[1]) * (i+1) / steps
                    
                    # Move eyes
                    move_servo_safe(2, v_pos)
                    move_servo_safe(3, h_pos)
                    
                    time.sleep(0.02)
                
                # Update current gaze
                current_gaze = (new_v, new_h)
                last_gaze_change = current_time
            
            # Small micro-movements while focusing
            if random.random() < 0.1:
                # Tiny random movements while maintaining focus
                micro_v = current_gaze[0] + random.uniform(-5, 5)
                micro_h = current_gaze[1] + random.uniform(-5, 5)
                
                move_servo_safe(2, micro_v)
                move_servo_safe(3, micro_h)
                
                # Return to main gaze after a short time
                time.sleep(0.1)
                move_servo_safe(2, current_gaze[0])
                move_servo_safe(3, current_gaze[1])
            
            time.sleep(0.05)
    
    except KeyboardInterrupt:
        print("Human eyes mode interrupted")
    finally:
        # Return to neutral position
        eyes_neutral()
        human_eyes_active = False

def stop_human_eyes():
    """Stop the human eyes simulation"""
    global human_eyes_active
    human_eyes_active = False
    print("Stopping human eyes mode...")

# ============================================================================
# MENU SYSTEM
# ============================================================================
def show_menu():
    print("\n" + "="*50)
    print("EYE MECHANISM CONTROL MENU")
    print("="*50)
    print("1. Run Bounds Detection Routine")
    print("2. Make Eyes Blink")
    print("3. Make Eyes Look Up")
    print("4. Make Eyes Look Down")
    print("5. Make Eyes Look Left")
    print("6. Make Eyes Look Right")
    print("7. Return to Neutral Position")
    print("8. Human Eyes (Natural Movement)")
    print("9. Exit")
    print("="*50)

# ============================================================================
# PLOTTING FUNCTIONS
# ============================================================================
def update_plot(frame):
    """Update the live current plot - called by animation"""
    if current_data and time_data:
        plt.cla()  # Clear axis instead of figure for better performance
        
        # Plot current data
        plt.plot(list(time_data), list(current_data), 'b-', linewidth=1)
        
        # Add threshold lines
        plt.axhline(y=current_threshold, color='r', linestyle='--', label=f'Default Threshold ({current_threshold}mA)')
        plt.axhline(y=servo2_threshold, color='g', linestyle='--', label=f'Servo 2 Threshold ({servo2_threshold}mA)')
        plt.axhline(y=servo3_threshold, color='orange', linestyle='--', label=f'Servo 3 Threshold ({servo3_threshold}mA)')
        
        # Set labels and title
        plt.xlabel('Time (s)')
        plt.ylabel('Current (mA)')
        
        if bounds_detected:
            title = "All Servo Bounds Detected | "
            for i in range(6):
                bounds = servo_bounds[i]
                title += f"S{i}:{bounds['min']:.0f}-{bounds['max']:.0f}° "
            title += f"| Current: {current_data[-1]:.2f}mA"
        else:
            title = f'Detecting Limits for All Servos... | Current: {current_data[-1]:.2f}mA'
        
        # Add command status to title
        if command_in_progress:
            title += " | Command in progress..."
        if human_eyes_active:
            title += " | Human Eyes Active"
        
        plt.title(title)
        plt.grid(True, alpha=0.3)
        plt.legend(loc='upper right')
        
        # Set x-axis to show last 30 seconds
        if time_data:
            plt.xlim(max(0, time_data[-1]-30), time_data[-1]+1)
        
        plt.tight_layout()
    
    return []

# ============================================================================
# MAIN PROGRAM
# ============================================================================
if __name__ == "__main__":
    if not init_ina231():
        exit(1)
    
    # Start data collection
    threading.Thread(target=data_collector, daemon=True).start()
    
    # Setup live plotting with animation
    plt.ion()
    fig = plt.figure(figsize=(10, 6))
    
    # Create animation
    ani = animation.FuncAnimation(fig, update_plot, interval=100, blit=True, cache_frame_data=False)
    
    # Show the plot window but don't block
    plt.show(block=False)
    
    # Start in neutral position
    print("Initialization complete. Starting menu system...")
    eyes_neutral()
    
    try:
        # Main loop with menu in the main thread
        while running:
            show_menu()
            choice = input("Enter your choice (1-9): ").strip()
            
            if choice == "1":
                # Run bounds detection in a separate thread
                bounds_thread = threading.Thread(target=detect_all_bounds, daemon=True)
                bounds_thread.start()
                print("Bounds detection started in background...")
                
            elif choice == "2":
                # Run blink in a separate thread
                blink_thread = threading.Thread(target=eyes_blink, daemon=True)
                blink_thread.start()
                print("Blink command started...")
                
            elif choice == "3":
                # Run look up in a separate thread
                look_up_thread = threading.Thread(target=eyes_look_up, daemon=True)
                look_up_thread.start()
                print("Look up command started...")
                
            elif choice == "4":
                # Run look down in a separate thread
                look_down_thread = threading.Thread(target=eyes_look_down, daemon=True)
                look_down_thread.start()
                print("Look down command started...")
                
            elif choice == "5":
                # Run look left in a separate thread
                look_left_thread = threading.Thread(target=eyes_look_left, daemon=True)
                look_left_thread.start()
                print("Look left command started...")
                
            elif choice == "6":
                # Run look right in a separate thread
                look_right_thread = threading.Thread(target=eyes_look_right, daemon=True)
                look_right_thread.start()
                print("Look right command started...")
                
            elif choice == "7":
                # Run neutral in a separate thread
                neutral_thread = threading.Thread(target=eyes_neutral, daemon=True)
                neutral_thread.start()
                print("Neutral position command started...")
                
            elif choice == "8":
                if human_eyes_active:
                    stop_human_eyes()
                else:
                    # Run human eyes in a separate thread
                    human_eyes_thread = threading.Thread(target=human_eyes, daemon=True)
                    human_eyes_thread.start()
                    print("Human eyes mode started...")
                
            elif choice == "9":
                print("Exiting program...")
                running = False
                human_eyes_active = False
                break
                
            else:
                print("Invalid choice. Please enter a number between 1-9.")
            
            # Process any pending GUI events to keep the plot responsive
            plt.pause(0.001)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        running = False
        human_eyes_active = False
        plt.close('all')
        print("Program exited safely.")
        if bounds_detected:
            print("\nFinal Servo Bounds and Positions:")
            for servo_num in range(6):
                bounds = servo_bounds[servo_num]
                print(f"Servo {servo_num}: {bounds['min']:.1f}° to {bounds['max']:.1f}° (Center: {bounds['center']:.1f}°)")