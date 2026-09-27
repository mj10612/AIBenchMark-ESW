# Task: I2C Temperature Sensor Driver with Mock HAL

You are an embedded software engineer. Implement a reliable device driver for an I2C digital temperature sensor.

## Hardware Specifications
- Device address: `SENSOR_DEFAULT_I2C_ADDR` (`0x48`)
- Registers:
  - `SENSOR_REG_WHO_AM_I` (`0x0F`): Read-only, returns `0xA5`.
  - `SENSOR_REG_CONFIG` (`0x02`): Read/Write, 8-bit config (set bit 0 to `1` to enable normal mode).
  - `SENSOR_REG_TEMP_MSB` (`0x00`) and `SENSOR_REG_TEMP_LSB` (`0x01`): 12-bit signed temperature.
    - Temperature format: `((MSB << 8) | LSB) >> 4` (12-bit signed integer in two's complement).
    - Resolution: Each LSB represents $0.0625^\circ\text{C}$ (i.e. $1/16^\circ\text{C}$).
    - Result output: Fixed-point centidegrees Celsius ($\times 100$), e.g. $25.0625^\circ\text{C} \approx 2506$.

## Error Handling:
- Return `SENSOR_ERR_NULL_PARAM` if any pointer (`dev`, `bus`, `bus->read`, `bus->write`, `temp_celsius_x100`) is NULL.
- Return `SENSOR_ERR_COMM_FAIL` if any I2C read/write operation returns a non-OK status.
- Return `SENSOR_ERR_INVALID_ID` if the chip ID in `WHO_AM_I` register is not `0xA5`.
- In `sensor_read_temperature_celsius_x100`, if `dev->is_initialized` is false, return `SENSOR_ERR_COMM_FAIL`.

Implement `sensor_init` and `sensor_read_temperature_celsius_x100` in `src/i2c_sensor.c`.
