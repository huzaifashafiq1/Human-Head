import os
os.environ["BLINKA_FT232H"] = "1"

import struct
import time
import threading
import matplotlib.pyplot as plt
from collections import deque
import board
import busio
from adafruit_pca9685 import PCA9685
import random
import math
from adafruit_motor import servo 

############################################
# Shared I2C bus
############################################
i2c = busio.I2C(board.SCL, board.SDA)

############################################
# INA231 Current Monitor Setup
############################################
INA231_ADDRESS = 0x40
INA231_CONFIG_REG = 0x00
INA231_CURRENT = 0x04
INA231_CALIBRATION = 0x05
INA231_CONFIG_DEFAULT = 0x4527
INA231_CALIBRATION_VAL = 0x0A00

current_data = deque(maxlen=1000)
time_data = deque(maxlen=1000)
current_monitor_running = False
plot_mode = False  # True = interactive mode, False = menu mode
plot_fig = None
start_time = time.time()

def write_ina231(reg, value):
    try:
        data = struct.pack('>BH', reg, value)
        i2c.writeto(INA231_ADDRESS, data)
        return True
    except Exception as e:
        print(f"INA231 Write error: {e}")
        return False

def read_ina231(reg):
    try:
        i2c.writeto(INA231_ADDRESS, bytes([reg]))
        result = bytearray(2)
        i2c.readfrom_into(INA231_ADDRESS, result)
        return struct.unpack('>H', result)[0]
    except Exception as e:
        print(f"INA231 Read error: {e}")
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
    global current_monitor_running
    while current_monitor_running:
        try:
            current_mA = read_current()
            elapsed_time = time.time() - start_time
            current_data.append(current_mA)
            time_data.append(elapsed_time)
            time.sleep(0.05)
        except Exception as e:
            print(f"Data read error: {e}")
            time.sleep(0.1)

def update_plot():
    """Update plot - to be called from main thread"""
    global plot_fig
    try:
        if plot_fig is not None and plt.fignum_exists(plot_fig.number):
            plt.figure(plot_fig.number)
            plt.clf()
            
            if current_data and time_data:
                # Plot the data like in original code
                plt.plot(list(time_data), list(current_data), 'b-', label='Current (mA)')
                plt.xlabel('Time (s)')
                plt.ylabel('Current (mA)')
                plt.title(f'Live Current - Latest: {current_data[-1]:.2f} mA')
                plt.grid(True, alpha=0.3)
                plt.legend()
                if time_data:
                    plt.xlim(max(0, time_data[-1]-30), time_data[-1]+1)
            else:
                # Show empty plot with proper labels when no data yet
                plt.plot([], [], 'b-', label='Current (mA)')
                plt.xlabel('Time (s)')
                plt.ylabel('Current (mA)')
                plt.title('Live Current Monitor - Waiting for data...')
                plt.grid(True, alpha=0.3)
                plt.legend()
                plt.xlim(0, 30)
                plt.ylim(-10, 10)
            
            plt.tight_layout()
            plt.draw()
            return True
        return False
    except Exception as e:
        print(f"Plot update error: {e}")
        return False

############################################
# Eye Controller Setup
############################################
# Initialize PCA9685
pca = PCA9685(i2c, address=0x42)
pca.frequency = 50  # Typical servo frequency

# All eye positions and limits
neutral_positions = [70, 110, 90, 90, 110, 80]
min_angles = [60.0, 30.0, 70.0, 50.0, 40.0, 30.0]
max_angles = [130.0, 150.0, 130.0, 130.0, 120.0, 140.0]

# Eye expressions
blink_positions = [129.82, 44.61, None, None, 39.78, 129.82]

# Initialize servo objects
servos = []
for i in range(6):
    servos.append(servo.Servo(pca.channels[i], min_pulse=500, max_pulse=2500))

class HumanEyeController:
    def __init__(self):
        self.current_gaze = {'up_down': 90, 'left_right': 90}
        self.gaze_target = {'up_down': 90, 'left_right': 90}
        self.last_blink_time = time.time()
        self.last_movement_time = time.time()
        self.movement_phase = 0
        self.blink_interval = random.uniform(1.5, 6.0)
        self.in_saccade = False
        self.saccade_start_time = 0
        self.saccade_duration = 0
        self.micro_movements = True
        self.running = False
        
    def smooth_move_to_angle(self, servo_index, target_angle, speed=0.02):
        """Smooth servo movement with natural acceleration/deceleration"""
        if target_angle is None:
            return
            
        current = servos[servo_index].angle
        diff = target_angle - current
        
        if abs(diff) < 0.5:
            return
            
        # Natural movement curve (ease in/out)
        step = diff * speed
        servos[servo_index].angle = current + step
    
    def generate_natural_gaze_target(self):
        """Generate natural human-like gaze targets"""
        movement_types = [
            'center_drift',      # 40% - small movements around center
            'horizontal_scan',   # 25% - left-right scanning
            'vertical_check',    # 20% - up-down movements
            'diagonal_glance',   # 10% - diagonal movements
            'fixation_return'    # 5% - return to center
        ]
        
        weights = [0.4, 0.25, 0.2, 0.1, 0.05]
        movement_type = random.choices(movement_types, weights=weights)[0]
        
        if movement_type == 'center_drift':
            up_down = random.uniform(85, 95)
            left_right = random.uniform(85, 95)
        elif movement_type == 'horizontal_scan':
            up_down = random.uniform(88, 92)
            left_right = random.uniform(min_angles[3] + 10, max_angles[3] - 10)
        elif movement_type == 'vertical_check':
            up_down = random.uniform(min_angles[2] + 5, max_angles[2] - 5)
            left_right = random.uniform(85, 95)
        elif movement_type == 'diagonal_glance':
            up_down = random.uniform(min_angles[2] + 10, max_angles[2] - 10)
            left_right = random.uniform(min_angles[3] + 10, max_angles[3] - 10)
        else:  # fixation_return
            up_down = 90
            left_right = 90
        
        return up_down, left_right
    
    def execute_saccade(self, target_up_down, target_left_right):
        """Execute rapid eye movement (saccade)"""
        self.in_saccade = True
        self.saccade_start_time = time.time()
        
        distance = math.sqrt((target_up_down - self.current_gaze['up_down'])**2 + 
                           (target_left_right - self.current_gaze['left_right'])**2)
        self.saccade_duration = 0.1 + (distance / 100) * 0.3
        
        self.gaze_target['up_down'] = target_up_down
        self.gaze_target['left_right'] = target_left_right
    
    def update_eye_position(self):
        """Update eye position with smooth, natural movement"""
        current_time = time.time()
        
        if self.in_saccade:
            elapsed = current_time - self.saccade_start_time
            if elapsed >= self.saccade_duration:
                self.in_saccade = False
                self.current_gaze['up_down'] = self.gaze_target['up_down']
                self.current_gaze['left_right'] = self.gaze_target['left_right']
            else:
                progress = elapsed / self.saccade_duration
                eased_progress = 0.5 * (1 - math.cos(progress * math.pi))
                
                self.current_gaze['up_down'] = (
                    self.current_gaze['up_down'] + 
                    (self.gaze_target['up_down'] - self.current_gaze['up_down']) * eased_progress * 0.3
                )
                self.current_gaze['left_right'] = (
                    self.current_gaze['left_right'] + 
                    (self.gaze_target['left_right'] - self.current_gaze['left_right']) * eased_progress * 0.3
                )
        
        # Add micro-movements
        if self.micro_movements and not self.in_saccade:
            micro_up_down = random.uniform(-0.5, 0.5)
            micro_left_right = random.uniform(-0.5, 0.5)
            self.current_gaze['up_down'] += micro_up_down
            self.current_gaze['left_right'] += micro_left_right
        
        # Apply constraints
        self.current_gaze['up_down'] = max(min_angles[2], min(self.current_gaze['up_down'], max_angles[2]))
        self.current_gaze['left_right'] = max(min_angles[3], min(self.current_gaze['left_right'], max_angles[3]))
        
        # Move servos
        try:
            servos[2].angle = self.current_gaze['up_down']
            servos[3].angle = self.current_gaze['left_right']
        except Exception as e:
            print(f"Servo movement error: {e}")
    
    def blink_both_eyes(self, duration=0.15):
        """Natural eye blink with proper timing"""
        try:
            # Pre-blink: slight eyelid tension
            pre_blink_positions = [
                neutral_positions[0] + 2, neutral_positions[1] - 2, None, None,
                neutral_positions[4] - 2, neutral_positions[5] + 2
            ]
            for i, pos in enumerate(pre_blink_positions):
                if pos is not None:
                    servos[i].angle = pos
            time.sleep(0.02)
            
            # Main blink - close eyes
            for i, pos in enumerate(blink_positions):
                if pos is not None:
                    servos[i].angle = pos
            time.sleep(duration)
            
            # Open eyes with slight overshoot
            overshoot_positions = [
                neutral_positions[0] - 3, neutral_positions[1] + 3, None, None,
                neutral_positions[4] + 3, neutral_positions[5] - 3
            ]
            for i, pos in enumerate(overshoot_positions):
                if pos is not None:
                    servos[i].angle = pos
            time.sleep(0.05)
            
            # Return to neutral
            for i, pos in enumerate(neutral_positions):
                if i in [0, 1, 4, 5]:
                    servos[i].angle = pos
            time.sleep(0.1)
        except Exception as e:
            print(f"Blink error: {e}")
    
    def double_blink(self):
        """Execute a double blink"""
        self.blink_both_eyes(0.1)
        time.sleep(0.15)
        self.blink_both_eyes(0.12)
    
    def should_blink(self):
        """Determine if it's time to blink"""
        current_time = time.time()
        time_since_last = current_time - self.last_blink_time
        
        if time_since_last >= self.blink_interval:
            self.blink_interval = random.uniform(1.2, 7.0)
            if random.random() < 0.15:
                return 'double'
            else:
                return 'single'
        return None
    
    def should_move_gaze(self):
        """Determine if it's time for a new gaze movement"""
        current_time = time.time()
        time_since_last = current_time - self.last_movement_time
        
        base_interval = random.uniform(0.8, 4.0)
        if random.random() < 0.05:
            base_interval *= 2
        
        return time_since_last >= base_interval
    
    def run_human_like_behavior(self):
        """Main loop for human-like eye behavior"""
        # Initialize to neutral
        try:
            for i, angle in enumerate(neutral_positions):
                servos[i].angle = angle
            time.sleep(1)
        except Exception as e:
            print(f"Servo initialization error: {e}")
            return
        
        self.running = True
        print("✓ Eye animation started!")
        
        try:
            while self.running:
                current_time = time.time()
                
                # Check for blinking
                blink_type = self.should_blink()
                if blink_type:
                    if blink_type == 'double':
                        self.double_blink()
                    else:
                        self.blink_both_eyes(random.uniform(0.12, 0.18))
                    self.last_blink_time = current_time
                
                # Check for gaze movement
                if self.should_move_gaze() and not self.in_saccade:
                    target_up_down, target_left_right = self.generate_natural_gaze_target()
                    self.execute_saccade(target_up_down, target_left_right)
                    self.last_movement_time = current_time
                
                # Update eye position
                self.update_eye_position()
                
                time.sleep(0.02)  # 50 FPS update rate
                
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"Eye controller error: {e}")
        
        # Return to neutral when stopping
        try:
            for i, angle in enumerate(neutral_positions):
                servos[i].angle = angle
            print("✓ Eyes returned to neutral position")
        except Exception as e:
            print(f"Error returning to neutral: {e}")
    
    def stop(self):
        """Stop the eye animation"""
        self.running = False

############################################
# Combined Control Functions
############################################
def start_current_monitor():
    """Start the current monitoring system"""
    global current_monitor_running, start_time, plot_fig
    if not current_monitor_running:
        if init_ina231():
            current_monitor_running = True
            start_time = time.time()
            # Clear old data
            current_data.clear()
            time_data.clear()
            
            # Initialize plot in main thread
            plt.ion()
            plot_fig = plt.figure(figsize=(10, 6))
            
            # Draw initial empty plot with proper labels
            update_plot()
            
            # Start data collection thread only
            threading.Thread(target=data_collector_thread, daemon=True).start()
            print("✓ Current monitor started!")
            print("  Note: Use option 8 for live plot updates, or the plot will update when you return to menu")
            return True
        else:
            print("✗ Failed to initialize INA231")
            return False
    else:
        print("Current monitor is already running!")
        return True

def stop_current_monitor():
    """Stop the current monitoring system"""
    global current_monitor_running, plot_fig
    current_monitor_running = False
    if plot_fig is not None:
        plt.close(plot_fig)
        plot_fig = None
    print("✓ Current monitor stopped!")

def start_eyes():
    """Start the eye animation"""
    if not eye_controller.running:
        threading.Thread(target=eye_controller.run_human_like_behavior, daemon=True).start()
    else:
        print("Eye animation is already running!")

def stop_eyes():
    """Stop the eye animation"""
    eye_controller.stop()
    print("✓ Eye animation stopped!")

############################################
# Main Program
############################################
if __name__ == "__main__":
    eye_controller = HumanEyeController()
    
    print("=== COMBINED EYE CONTROLLER & CURRENT MONITOR ===")
    print("1. Start eye animation only")
    print("2. Start current monitor only") 
    print("3. Start both eye animation and current monitor")
    print("4. Stop eye animation")
    print("5. Stop current monitor")
    print("6. Stop both")
    print("7. Status")
    print("8. Interactive current monitor (live plot)")
    print("9. Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-9): ").strip()
            
            if choice == '1':
                start_eyes()
                
            elif choice == '2':
                start_current_monitor()
                
            elif choice == '3':
                print("Starting both systems...")
                start_current_monitor()
                time.sleep(0.5)  # Brief delay
                start_eyes()
                print("✓ Both systems started!")
                
            elif choice == '4':
                stop_eyes()
                
            elif choice == '5':
                stop_current_monitor()
                
            elif choice == '6':
                print("Stopping both systems...")
                stop_eyes()
                stop_current_monitor()
                print("✓ Both systems stopped!")
                
            elif choice == '7':
                print(f"Eye animation: {'Running' if eye_controller.running else 'Stopped'}")
                print(f"Current monitor: {'Running' if current_monitor_running else 'Stopped'}")
                if current_data:
                    print(f"Latest current reading: {current_data[-1]:.2f} mA")
                    
            elif choice == '8':
                if current_monitor_running:
                    print("Entering interactive mode... (Close plot window or press Ctrl+C to return to menu)")
                    try:
                        # Continuous plot updates in main thread like original code
                        while current_monitor_running:
                            if not update_plot():
                                current_monitor_running = False
                                break
                            plt.pause(0.05)  # Same timing as original code
                    except KeyboardInterrupt:
                        print("\nReturning to menu...")
                    except Exception as e:
                        print(f"Interactive mode error: {e}")
                else:
                    print("Please start current monitor first (option 2 or 3)")
                
            elif choice == '9':
                if eye_controller.running:
                    stop_eyes()
                if current_monitor_running:
                    stop_current_monitor()
                print("Exiting...")
                break
                
            else:
                print("Invalid choice, please try again.")
                
            # Update plot once after each menu choice if monitor is running
            if current_monitor_running and choice not in ['8', '9']:
                update_plot()
                plt.pause(0.01)
                
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            if eye_controller.running:
                stop_eyes()
            if current_monitor_running:
                stop_current_monitor()
            print("Program exited safely.")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")