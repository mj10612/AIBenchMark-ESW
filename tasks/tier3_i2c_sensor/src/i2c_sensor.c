#include "i2c_sensor.h"

sensor_status_t sensor_init(sensor_device_t* dev, const i2c_bus_t* bus) {
    (void)dev;
    (void)bus;
    return SENSOR_ERR_COMM_FAIL;
}

sensor_status_t sensor_read_temperature_celsius_x100(sensor_device_t* dev, int16_t* temp_celsius_x100) {
    (void)dev;
    (void)temp_celsius_x100;
    return SENSOR_ERR_COMM_FAIL;
}
