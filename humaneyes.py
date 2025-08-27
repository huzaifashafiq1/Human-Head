import os
os.environ["BLINKA_FT232H"] = "1"

import board
import busio
from adafruit_pca9685 import PCA9685
import time
import random
import math
from adafruit_motor import servo

# Create I2C bus using FT232H pins
i2c = busio.I2C(board.SCL, board.SDA)

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
        self.blink_interval = random.uniform(1.5, 6.0)  # More human-like blink rate
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
        # Human eye movement patterns
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
            # Small movements around center (most common)
            up_down = random.uniform(85, 95)
            left_right = random.uniform(85, 95)
            
        elif movement_type == 'horizontal_scan':
            # Horizontal scanning movement
            up_down = random.uniform(88, 92)  # Keep vertical centered
            left_right = random.uniform(min_angles[3] + 10, max_angles[3] - 10)
            
        elif movement_type == 'vertical_check':
            # Vertical movements (looking up/down)
            up_down = random.uniform(min_angles[2] + 5, max_angles[2] - 5)
            left_right = random.uniform(85, 95)  # Keep horizontal centered
            
        elif movement_type == 'diagonal_glance':
            # Diagonal movements
            up_down = random.uniform(min_angles[2] + 10, max_angles[2] - 10)
            left_right = random.uniform(min_angles[3] + 10, max_angles[3] - 10)
            
        else:  # fixation_return
            # Return to neutral
            up_down = 90
            left_right = 90
        
        return up_down, left_right
    
    def execute_saccade(self, target_up_down, target_left_right):
        """Execute rapid eye movement (saccade)"""
        self.in_saccade = True
        self.saccade_start_time = time.time()
        
        # Calculate saccade duration based on distance (more realistic)
        distance = math.sqrt((target_up_down - self.current_gaze['up_down'])**2 + 
                           (target_left_right - self.current_gaze['left_right'])**2)
        self.saccade_duration = 0.1 + (distance / 100) * 0.3  # 0.1-0.4 seconds
        
        self.gaze_target['up_down'] = target_up_down
        self.gaze_target['left_right'] = target_left_right
    
    def update_eye_position(self):
        """Update eye position with smooth, natural movement"""
        current_time = time.time()
        
        if self.in_saccade:
            # Fast saccadic movement
            elapsed = current_time - self.saccade_start_time
            if elapsed >= self.saccade_duration:
                self.in_saccade = False
                self.current_gaze['up_down'] = self.gaze_target['up_down']
                self.current_gaze['left_right'] = self.gaze_target['left_right']
            else:
                # Smooth saccade progression
                progress = elapsed / self.saccade_duration
                # Use easing function for natural acceleration/deceleration
                eased_progress = 0.5 * (1 - math.cos(progress * math.pi))
                
                self.current_gaze['up_down'] = (
                    self.current_gaze['up_down'] + 
                    (self.gaze_target['up_down'] - self.current_gaze['up_down']) * eased_progress * 0.3
                )
                self.current_gaze['left_right'] = (
                    self.current_gaze['left_right'] + 
                    (self.gaze_target['left_right'] - self.current_gaze['left_right']) * eased_progress * 0.3
                )
        
        # Add micro-movements (fixational eye movements)
        if self.micro_movements and not self.in_saccade:
            micro_up_down = random.uniform(-0.5, 0.5)
            micro_left_right = random.uniform(-0.5, 0.5)
            self.current_gaze['up_down'] += micro_up_down
            self.current_gaze['left_right'] += micro_left_right
        
        # Apply constraints
        self.current_gaze['up_down'] = max(min_angles[2], min(self.current_gaze['up_down'], max_angles[2]))
        self.current_gaze['left_right'] = max(min_angles[3], min(self.current_gaze['left_right'], max_angles[3]))
        
        # Move servos
        servos[2].angle = self.current_gaze['up_down']
        servos[3].angle = self.current_gaze['left_right']
    
    def blink_both_eyes(self, duration=0.15):
        """Natural eye blink with proper timing"""
        # Pre-blink: slight eyelid tension (very subtle)
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
        
        # Open eyes with slight overshoot (natural reflex)
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
            if i in [0, 1, 4, 5]:  # Only eyelids
                servos[i].angle = pos
        time.sleep(0.1)
    
    def double_blink(self):
        """Execute a double blink (two quick blinks in succession)"""
        self.blink_both_eyes(0.1)  # First blink - shorter
        time.sleep(0.15)           # Brief pause
        self.blink_both_eyes(0.12) # Second blink - slightly longer
    
    def should_blink(self):
        """Determine if it's time to blink based on natural patterns"""
        current_time = time.time()
        time_since_last = current_time - self.last_blink_time
        
        if time_since_last >= self.blink_interval:
            # Reset blink timer with natural variation
            self.blink_interval = random.uniform(1.2, 7.0)
            
            # 15% chance of double blink
            if random.random() < 0.15:
                return 'double'
            else:
                return 'single'
        
        return None
    
    def should_move_gaze(self):
        """Determine if it's time for a new gaze movement"""
        current_time = time.time()
        time_since_last = current_time - self.last_movement_time
        
        # Vary movement intervals (0.8 to 4 seconds)
        base_interval = random.uniform(0.8, 4.0)
        
        # Occasionally have longer fixations (5% chance)
        if random.random() < 0.05:
            base_interval *= 2
        
        return time_since_last >= base_interval
    
    def run_human_like_behavior(self):
        """Main loop for human-like eye behavior"""
        # Initialize to neutral
        for i, angle in enumerate(neutral_positions):
            servos[i].angle = angle
        time.sleep(1)
        
        self.running = True
        
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
                
                # Control loop timing
                time.sleep(0.02)  # 50 FPS update rate
                
        except KeyboardInterrupt:
            pass
        
        # Return to neutral when stopping
        for i, angle in enumerate(neutral_positions):
            servos[i].angle = angle
    
    def stop(self):
        """Stop the eye animation"""
        self.running = False

# Control interface
def start_eyes():
    """Start the eye animation"""
    eye_controller.run_human_like_behavior()

def stop_eyes():
    """Stop the eye animation"""
    eye_controller.stop()

# Main execution with menu
if __name__ == "__main__":
    eye_controller = HumanEyeController()
    
    print("=== EYE ANIMATION CONTROL ===")
    print("1. Start human-like eye behavior")
    print("2. Stop eye animation")
    print("3. Exit")
    
    while True:
        choice = input("\nEnter your choice (1-3): ")
        
        if choice == '1':
            if not eye_controller.running:
                print("Starting eye animation... (Press Ctrl+C to stop)")
                try:
                    start_eyes()
                    print("Eye animation stopped.")
                except KeyboardInterrupt:
                    stop_eyes()
                    print("\nEye animation stopped.")
            else:
                print("Eye animation is already running!")
                
        elif choice == '2':
            if eye_controller.running:
                stop_eyes()
                print("Eye animation stopped.")
            else:
                print("Eye animation is not running.")
                
        elif choice == '3':
            if eye_controller.running:
                stop_eyes()
            print("Exiting...")
            break
            
        else:
            print("Invalid choice, please try again.")