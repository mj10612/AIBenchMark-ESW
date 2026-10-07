/* AIBENCHMARK_ESW_CANARY_V1_tier3_i2c_sensor */
#ifndef MOCK_I2C_H
#define MOCK_I2C_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    I2C_STATUS_OK = 0,
    I2C_STATUS_ERROR_NACK,
    I2C_STATUS_ERROR_TIMEOUT,
    I2C_STATUS_ERROR_BUS_BUSY
} i2c_status_t;

/* HAL abstraction function pointer types */
typedef i2c_status_t (*i2c_read_fn)(uint8_t dev_addr, uint8_t reg_addr, uint8_t* data, size_t len);
typedef i2c_status_t (*i2c_write_fn)(uint8_t dev_addr, uint8_t reg_addr, const uint8_t* data, size_t len);

typedef struct {
    uint8_t dev_addr;
    i2c_read_fn read;
    i2c_write_fn write;
} i2c_bus_t;

#ifdef __cplusplus
}
#endif

#endif /* MOCK_I2C_H */
