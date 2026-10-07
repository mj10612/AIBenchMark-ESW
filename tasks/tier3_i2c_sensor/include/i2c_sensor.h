/* AIBENCHMARK_ESW_CANARY_V1_tier3_i2c_sensor */
#ifndef I2C_SENSOR_H
#define I2C_SENSOR_H

#include "mock_i2c.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SENSOR_DEFAULT_I2C_ADDR   0x48
#define SENSOR_REG_TEMP_MSB       0x00
#define SENSOR_REG_TEMP_LSB       0x01
#define SENSOR_REG_CONFIG         0x02
#define SENSOR_REG_WHO_AM_I       0x0F
#define SENSOR_EXPECTED_CHIP_ID   0xA5

typedef enum {
    SENSOR_OK = 0,
    SENSOR_ERR_NULL_PARAM,
    SENSOR_ERR_COMM_FAIL,
    SENSOR_ERR_INVALID_ID
} sensor_status_t;

typedef struct {
    const i2c_bus_t* bus;
    bool is_initialized;
} sensor_device_t;

sensor_status_t sensor_init(sensor_device_t* dev, const i2c_bus_t* bus);
sensor_status_t sensor_read_temperature_celsius_x100(sensor_device_t* dev, int16_t* temp_celsius_x100);

#ifdef __cplusplus
}
#endif

#endif /* I2C_SENSOR_H */
