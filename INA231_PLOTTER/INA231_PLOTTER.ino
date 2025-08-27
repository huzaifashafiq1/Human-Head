// INA231 Current Sensor for Serial Plotter
// Monitors servo current draw with high precision
// Connections: VCC->3.3V, GND->GND, SDA->A4, SCL->A5

#include <Wire.h>

// INA231 I2C address (default 0x40, can be 0x41-0x4F depending on A0/A1 pins)
#define INA231_ADDRESS 0x40

// INA231 Register addresses
#define INA231_CONFIG_REG       0x00
#define INA231_SHUNT_VOLTAGE    0x01
#define INA231_BUS_VOLTAGE      0x02
#define INA231_POWER            0x03
#define INA231_CURRENT          0x04
#define INA231_CALIBRATION      0x05

// Configuration values
#define INA231_CONFIG_DEFAULT   0x4527  // 16 averages, 1.1ms conversion time
#define INA231_CALIBRATION_VAL  0x0A00  // For 0.1 ohm shunt, 1A max current

// Variables for baseline and amplification
float baselineCurrent = 0;
float baselineVoltage = 0;
bool baselineSet = false;
unsigned long baselineStartTime = 0;

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    delay(1);
  }
  
  Serial.println("INA231 Current Sensor - Serial Plotter");
  
  Wire.begin();
  
  // Initialize INA231
  if (!initINA231()) {
    Serial.println("Failed to find INA231 chip");
    while (1) { delay(10); }
  }
  
  Serial.println("INA231 Ready - Establishing Baseline...");
  baselineStartTime = millis();
}

void loop() {
  // Read sensor values
  float busvoltage = readBusVoltage();
  float shuntvoltage = readShuntVoltage();
  float current_mA = readCurrent();
  float power_mW = readPower();
  
  // Calculate load voltage
  float loadvoltage = busvoltage + shuntvoltage;
  
  // Set baseline after 2 seconds
  if (!baselineSet && millis() - baselineStartTime > 2000) {
    baselineCurrent = current_mA;
    baselineVoltage = loadvoltage;
    baselineSet = true;
    Serial.println("Baseline established");
    delay(500);
    return;
  }
  
  // Calculate changes from baseline
  float currentChange = current_mA - baselineCurrent;
  float voltageChange = loadvoltage - baselineVoltage;
  
  // Amplify changes for better visibility
  float amplifiedCurrent = currentChange * 5;  // 5x amplification
  float dramaticCurrent = currentChange * abs(currentChange) / 10; // Squared for spikes
  
  // Print values for Serial Plotter
  Serial.print("Current_mA:");
  Serial.print(current_mA, 2);
  Serial.print(",Current_Change_5x:");
  Serial.print(amplifiedCurrent, 2);
  Serial.print(",Current_Spike:");
  Serial.print(dramaticCurrent, 2);
  Serial.print(",Voltage:");
  Serial.print(loadvoltage, 3);
  Serial.print(",Power_mW:");
  Serial.print(power_mW, 2);
  Serial.print(",Baseline_Current:");
  Serial.print(baselineCurrent, 2);
  
  Serial.println();
  
  delay(25);  // Fast sampling for responsive plotting
}

// Initialize INA231
bool initINA231() {
  // Write configuration register
  if (!writeRegister(INA231_CONFIG_REG, INA231_CONFIG_DEFAULT)) {
    return false;
  }
  
  // Write calibration register
  if (!writeRegister(INA231_CALIBRATION, INA231_CALIBRATION_VAL)) {
    return false;
  }
  
  delay(10);
  return true;
}

// Read bus voltage (V)
float readBusVoltage() {
  uint16_t value = readRegister(INA231_BUS_VOLTAGE);
  return (value >> 3) * 0.00125; // 1.25mV per bit
}

// Read shunt voltage (V)
float readShuntVoltage() {
  int16_t value = (int16_t)readRegister(INA231_SHUNT_VOLTAGE);
  return value * 0.0000025; // 2.5µV per bit
}

// Read current (mA)
float readCurrent() {
  int16_t value = (int16_t)readRegister(INA231_CURRENT);
  return value * 0.001; // 1mA per bit with our calibration
}

// Read power (mW)
float readPower() {
  uint16_t value = readRegister(INA231_POWER);
  return value * 0.025; // 25mW per bit with our calibration
}

// Write to INA231 register
bool writeRegister(uint8_t reg, uint16_t value) {
  Wire.beginTransmission(INA231_ADDRESS);
  Wire.write(reg);
  Wire.write((value >> 8) & 0xFF);
  Wire.write(value & 0xFF);
  return (Wire.endTransmission() == 0);
}

// Read from INA231 register
uint16_t readRegister(uint8_t reg) {
  Wire.beginTransmission(INA231_ADDRESS);
  Wire.write(reg);
  Wire.endTransmission(false);
  
  Wire.requestFrom(INA231_ADDRESS, 2);
  uint16_t value = 0;
  if (Wire.available() >= 2) {
    value = (Wire.read() << 8) | Wire.read();
  }
  return value;
}