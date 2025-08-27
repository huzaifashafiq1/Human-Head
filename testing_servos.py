import os
os.environ["BLINKA_FT232H"] = "1"

import board
import busio
from adafruit_pca9685 import PCA9685
import time
from adafruit_motor import servo

# Create I2C bus using FT232H pins
i2c = busio.I2C(board.SCL, board.SDA)

# Initialize PCA9685
pca = PCA9685(i2c, address=0x42)
pca.frequency = 50  # Typical servo frequency

# Initialize servos for channels 8, 9, 10, and 11
servos = {}
available_channels = [8, 9, 10, 11]

for channel in available_channels:
    servos[channel] = servo.Servo(pca.channels[channel], min_pulse=500, max_pulse=2500)

def sweep_servo(channel, speed=0.1):
    """Sweep servo on specified channel through its full range"""
    if channel not in servos:
        print(f"Error: Channel {channel} not available. Use channels: {available_channels}")
        return
    
    print(f"Starting full range sweep on channel {channel}...")
    
    try:
        # Test the servo's actual range by finding its limits
        servo_obj = servos[channel]
        
        # Try to find the actual working range
        min_angle = 0
        max_angle = 180
        
        # Test for continuous rotation or extended range
        try:
            servo_obj.angle = 0
            time.sleep(0.2)
            servo_obj.angle = 180
            time.sleep(0.2)
            # If no errors, use standard range but try extended
            servo_obj.angle = None  # Try continuous rotation
            time.sleep(0.2)
            print(f"Channel {channel}: Attempting continuous rotation...")
            
            # Continuous rotation - sweep through duty cycle range
            for i in range(1000, 2001, 25):  # Pulse width in microseconds
                servo_obj._pwm_out.duty_cycle = int((i / 1000000) * 65535 * servo_obj._pwm_out.frequency)
                time.sleep(speed)
            
            # Reverse direction
            for i in range(2000, 999, -25):
                servo_obj._pwm_out.duty_cycle = int((i / 1000000) * 65535 * servo_obj._pwm_out.frequency)
                time.sleep(speed)
                
        except:
            # Standard servo - use angle control with extended range
            print(f"Channel {channel}: Standard servo detected, using full angle range...")
            
            # Try extended range (some servos go beyond 180°)
            try:
                # Sweep from 0 to maximum possible
                for angle in range(0, 271, 5):  # Try up to 270°
                    try:
                        servo_obj.angle = angle
                        time.sleep(speed)
                        max_angle = angle  # Keep track of highest successful angle
                    except:
                        break  # Stop if we hit the limit
                
                # Sweep back from maximum to 0
                for angle in range(max_angle, -1, -5):
                    try:
                        servo_obj.angle = angle
                        time.sleep(speed)
                    except:
                        break
                        
            except Exception as inner_e:
                print(f"Extended range failed, using standard 0-180°: {inner_e}")
                # Fallback to standard 0-180 sweep
                for angle in range(0, 181, 5):
                    servo_obj.angle = angle
                    time.sleep(speed)
                
                for angle in range(180, -1, -5):
                    servo_obj.angle = angle
                    time.sleep(speed)
        
        print(f"Full range sweep complete on channel {channel}!")
        
    except Exception as e:
        print(f"Error sweeping channel {channel}: {e}")

def sweep_all_channels(speed=0.1):
    """Sweep all available channels sequentially through their full range"""
    print("Starting full range sweep on all channels...")
    for channel in available_channels:
        print(f"\n--- Channel {channel} ---")
        sweep_servo(channel, speed)
        time.sleep(0.5)  # Brief pause between channels
    print("\nAll channels full range sweep complete!")

def sweep_channels_simultaneously(speed=0.1):
    """Sweep all channels at the same time through their full range"""
    print("Starting simultaneous full range sweep on all channels...")
    
    try:
        # First try extended range sweep (0-270°)
        max_successful_angle = 180
        
        # Test what's the maximum angle all servos can handle
        for test_angle in range(180, 271, 10):
            try:
                for channel in available_channels:
                    servos[channel].angle = test_angle
                max_successful_angle = test_angle
                time.sleep(0.1)
            except:
                break
        
        print(f"Maximum detected angle: {max_successful_angle}°")
        
        # Sweep from 0 to maximum detected angle
        for angle in range(0, max_successful_angle + 1, 5):
            for channel in available_channels:
                try:
                    servos[channel].angle = angle
                except:
                    pass  # Skip if this channel can't reach this angle
            time.sleep(speed)
        
        # Sweep from maximum back to 0
        for angle in range(max_successful_angle, -1, -5):
            for channel in available_channels:
                try:
                    servos[channel].angle = angle
                except:
                    pass  # Skip if this channel can't reach this angle
            time.sleep(speed)
        
        print("Simultaneous full range sweep complete!")
        
    except Exception as e:
        print(f"Error during simultaneous sweep: {e}")

def test_servo_ranges():
    """Test the maximum range for each servo individually"""
    print("Testing maximum range for each servo...")
    
    for channel in available_channels:
        print(f"\nTesting Channel {channel}:")
        max_angle = 180
        
        # Test increasing angles to find the limit
        for test_angle in range(180, 361, 10):  # Test up to 360°
            try:
                servos[channel].angle = test_angle
                time.sleep(0.1)
                max_angle = test_angle
            except Exception as e:
                print(f"  Maximum angle reached: {max_angle}°")
                break
        
        # Test if it's a continuous rotation servo
        try:
            servos[channel].angle = None
            print(f"  Channel {channel}: Continuous rotation servo detected!")
            servos[channel].angle = 90  # Return to center
        except:
            print(f"  Channel {channel}: Standard servo, max angle: {max_angle}°")
            servos[channel].angle = 90  # Return to center
        
        time.sleep(0.5)

def center_all_servos():
    """Move all servos to center position (90°)"""
    print("Moving all servos to center position (90°)...")
    for channel in available_channels:
        try:
            servos[channel].angle = 90
            print(f"Channel {channel}: Centered")
        except Exception as e:
            print(f"Error centering channel {channel}: {e}")

def interactive_control():
    """Interactive servo control"""
    print("\n=== MULTI-CHANNEL SERVO SWEEP CONTROLLER ===")
    print("Available channels: 8, 9, 10, 11")
    print("\nCommands:")
    print("- Enter channel number (8, 9, 10, 11): Full range sweep that channel")
    print("- 'all': Full range sweep all channels sequentially") 
    print("- 'sync': Full range sweep all channels simultaneously")
    print("- 'center': Move all servos to center (90°)")
    print("- 'test': Test maximum range for each servo")
    print("- 'fast': Set fast sweep speed")
    print("- 'slow': Set slow sweep speed")
    print("- 'quit': Exit")
    
    sweep_speed = 0.1  # Default speed
    
    while True:
        user_input = input(f"\nEnter command (current speed: {sweep_speed}s): ").strip().lower()
        
        if user_input == 'quit':
            break
        elif user_input == 'all':
            sweep_all_channels(sweep_speed)
        elif user_input == 'sync':
            sweep_channels_simultaneously(sweep_speed)
        elif user_input == 'center':
            center_all_servos()
        elif user_input == 'test':
            test_servo_ranges()
        elif user_input == 'fast':
            sweep_speed = 0.05
            print("Speed set to FAST (0.05s)")
        elif user_input == 'slow':
            sweep_speed = 0.2
            print("Speed set to SLOW (0.2s)")
        else:
            try:
                channel = int(user_input)
                if channel in available_channels:
                    sweep_servo(channel, sweep_speed)
                else:
                    print(f"Invalid channel. Available channels: {available_channels}")
            except ValueError:
                print("Invalid input. Enter a channel number (8-11) or command.")

if __name__ == "__main__":
    print("Multi-Channel Servo Sweep Controller")
    print("Initializing all servos to center position...")
    
    # Initialize all servos to center
    center_all_servos()
    time.sleep(1)
    
    interactive_control()
    
    # Return all servos to center before exiting
    print("\nReturning all servos to center position...")
    center_all_servos()