/* AIBENCHMARK_ESW_CANARY_V1_tier3_i2c_sensor */
#include "i2c_sensor.h"

sensor_status_t sensor_init(sensor_device_t* dev, const i2c_bus_t* bus) {
    if (dev == NULL) {
        return SENSOR_ERR_NULL_PARAM;
    }
    /* A failed re-initialization must never leave the old device usable. */
    dev->is_initialized = false;
    dev->bus = NULL;
    if (bus == NULL || bus->read == NULL || bus->write == NULL) {
        return SENSOR_ERR_NULL_PARAM;
    }

    uint8_t chip_id = 0;
    if (bus->read(bus->dev_addr, SENSOR_REG_WHO_AM_I, &chip_id, 1) != I2C_STATUS_OK) {
        return SENSOR_ERR_COMM_FAIL;
    }

    if (chip_id != SENSOR_EXPECTED_CHIP_ID) {
        return SENSOR_ERR_INVALID_ID;
    }

    uint8_t cfg_val = 0x01;
    if (bus->write(bus->dev_addr, SENSOR_REG_CONFIG, &cfg_val, 1) != I2C_STATUS_OK) {
        return SENSOR_ERR_COMM_FAIL;
    }

    dev->bus = bus;
    dev->is_initialized = true;
    return SENSOR_OK;
}

sensor_status_t sensor_read_temperature_celsius_x100(sensor_device_t* dev, int16_t* temp_celsius_x100) {
    if (dev == NULL || temp_celsius_x100 == NULL) {
        return SENSOR_ERR_NULL_PARAM;
    }

    if (!dev->is_initialized) {
        return SENSOR_ERR_COMM_FAIL;
    }
    if (dev->bus == NULL || dev->bus->read == NULL || dev->bus->write == NULL) {
        return SENSOR_ERR_NULL_PARAM;
    }

    uint8_t raw_data[2] = {0, 0};
    if (dev->bus->read(dev->bus->dev_addr, SENSOR_REG_TEMP_MSB, raw_data, 2) != I2C_STATUS_OK) {
        return SENSOR_ERR_COMM_FAIL;
    }

    int16_t raw12 = (int16_t)((((uint16_t)raw_data[0] << 8) | (uint16_t)raw_data[1]) >> 4);
    if ((raw12 & 0x0800) != 0) {
        raw12 -= 4096;
    }

    *temp_celsius_x100 = (int16_t)(((int32_t)raw12 * 25) / 4);
    return SENSOR_OK;
}
