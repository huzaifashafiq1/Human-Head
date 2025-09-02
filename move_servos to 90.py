import os
os.environ["BLINKA_FT232H"] = "1"
import board
import busio
import time
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

# Initialize I2C and PCA9685
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c, address=0x42)
pca.frequency = 50

# Create servo objects for channels 0-5
servos = []
for i in range(6):
    servos.append(servo.Servo(pca.channels[i], min_pulse=500, max_pulse=2500))

def move_all_to_90():
    """Move all servos (0-5) to 90 degree position"""
    print("Moving all servos to 90 degrees...")
    
    for i in range(6):
        servos[i].angle = 90
        print(f"Servo {i}: moved to 90°")
        time.sleep(0.1)  # Small delay between servo movements
    
    print("All servos positioned at 90 degrees!")

if __name__ == "__main__":
    try:
        move_all_to_90()
        
        # Keep the program running to maintain servo positions
        print("Press Ctrl+C to exit...")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")