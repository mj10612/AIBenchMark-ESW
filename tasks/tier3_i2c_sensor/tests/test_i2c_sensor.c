/* AIBENCHMARK_ESW_CANARY_V1_tier3_i2c_sensor */
#include "unity.h"
#include "i2c_sensor.h"
#include <string.h>

static uint8_t mock_regs[256];
static bool fail_next_read = false;
static bool fail_next_write = false;
static i2c_status_t failure_status = I2C_STATUS_ERROR_TIMEOUT;

static i2c_status_t mock_read(uint8_t dev_addr, uint8_t reg_addr, uint8_t* data, size_t len) {
    if (dev_addr != SENSOR_DEFAULT_I2C_ADDR) {
        return I2C_STATUS_ERROR_NACK;
    }
    if (fail_next_read) {
        fail_next_read = false;
        return failure_status;
    }
    for (size_t i = 0; i < len; i++) {
        data[i] = mock_regs[(uint8_t)(reg_addr + i)];
    }
    return I2C_STATUS_OK;
}

static i2c_status_t mock_write(uint8_t dev_addr, uint8_t reg_addr, const uint8_t* data, size_t len) {
    if (dev_addr != SENSOR_DEFAULT_I2C_ADDR) {
        return I2C_STATUS_ERROR_NACK;
    }
    if (fail_next_write) {
        fail_next_write = false;
        return failure_status;
    }
    for (size_t i = 0; i < len; i++) {
        mock_regs[(uint8_t)(reg_addr + i)] = data[i];
    }
    return I2C_STATUS_OK;
}

static i2c_bus_t bus = {
    .dev_addr = SENSOR_DEFAULT_I2C_ADDR,
    .read = mock_read,
    .write = mock_write
};

static sensor_device_t dev;

void setUp(void) {
    memset(mock_regs, 0, sizeof(mock_regs));
    mock_regs[SENSOR_REG_WHO_AM_I] = SENSOR_EXPECTED_CHIP_ID;
    fail_next_read = false;
    fail_next_write = false;
    failure_status = I2C_STATUS_ERROR_TIMEOUT;
    memset(&dev, 0, sizeof(dev));
}

void tearDown(void) {}

void test_successful_init(void) {
    TEST_ASSERT_EQUAL(SENSOR_OK, sensor_init(&dev, &bus));
    TEST_ASSERT_TRUE(dev.is_initialized);
    TEST_ASSERT_EQUAL_HEX8(0x01, mock_regs[SENSOR_REG_CONFIG]);
}

void test_init_invalid_chip_id(void) {
    mock_regs[SENSOR_REG_WHO_AM_I] = 0x55; /* Wrong ID */
    TEST_ASSERT_EQUAL(SENSOR_ERR_INVALID_ID, sensor_init(&dev, &bus));
    TEST_ASSERT_FALSE(dev.is_initialized);
}

void test_init_i2c_bus_error(void) {
    fail_next_read = true;
    TEST_ASSERT_EQUAL(SENSOR_ERR_COMM_FAIL, sensor_init(&dev, &bus));
    TEST_ASSERT_FALSE(dev.is_initialized);
}

void test_read_positive_temperature(void) {
    TEST_ASSERT_EQUAL(SENSOR_OK, sensor_init(&dev, &bus));

    /* 25.0 deg C -> raw12 = 400 (0x0190) -> (0x0190 << 4) = 0x1900 -> MSB=0x19, LSB=0x00 */
    mock_regs[SENSOR_REG_TEMP_MSB] = 0x19;
    mock_regs[SENSOR_REG_TEMP_LSB] = 0x00;

    int16_t temp = 0;
    TEST_ASSERT_EQUAL(SENSOR_OK, sensor_read_temperature_celsius_x100(&dev, &temp));
    TEST_ASSERT_EQUAL_INT(2500, temp);
}

void test_read_negative_temperature(void) {
    TEST_ASSERT_EQUAL(SENSOR_OK, sensor_init(&dev, &bus));

    /* -10.0 deg C -> raw12 = -160 (0xFF60 & 0x0FFF = 0x0F60) -> MSB=0xF6, LSB=0x00 */
    mock_regs[SENSOR_REG_TEMP_MSB] = 0xF6;
    mock_regs[SENSOR_REG_TEMP_LSB] = 0x00;

    int16_t temp = 0;
    TEST_ASSERT_EQUAL(SENSOR_OK, sensor_read_temperature_celsius_x100(&dev, &temp));
    TEST_ASSERT_EQUAL_INT(-1000, temp);
}

void test_read_before_init_fails(void) {
    int16_t temp = 0;
    TEST_ASSERT_EQUAL(SENSOR_ERR_COMM_FAIL, sensor_read_temperature_celsius_x100(&dev, &temp));
}

void test_null_params_safety(void) {
    int16_t temp = 0;
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL_PARAM, sensor_init(NULL, &bus));
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL_PARAM, sensor_init(&dev, NULL));
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL_PARAM, sensor_read_temperature_celsius_x100(NULL, &temp));
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL_PARAM, sensor_read_temperature_celsius_x100(&dev, NULL));
}

void test_temperature_range_and_fractional_values(void) {
    const int16_t raw_values[] = {-2048, -1600, -1, 0, 1, 1600, 2047};
    const int16_t expected[] = {-12800, -10000, -6, 0, 6, 10000, 12793};
    TEST_ASSERT_EQUAL(SENSOR_OK, sensor_init(&dev, &bus));
    for (size_t i = 0; i < sizeof(raw_values) / sizeof(raw_values[0]); i++) {
        uint16_t encoded = (uint16_t)(((uint16_t)raw_values[i] & 0x0FFFU) << 4);
        mock_regs[SENSOR_REG_TEMP_MSB] = (uint8_t)(encoded >> 8);
        mock_regs[SENSOR_REG_TEMP_LSB] = (uint8_t)encoded;
        int16_t temperature = 0;
        TEST_ASSERT_EQUAL(SENSOR_OK, sensor_read_temperature_celsius_x100(&dev, &temperature));
        TEST_ASSERT_EQUAL_INT(expected[i], temperature);
    }
}

void test_missing_bus_and_callbacks(void) {
    i2c_bus_t invalid = bus;
    invalid.read = NULL;
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL_PARAM, sensor_init(&dev, &invalid));
    invalid = bus;
    invalid.write = NULL;
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL_PARAM, sensor_init(&dev, &invalid));

    int16_t temperature = 1234;
    dev.is_initialized = true;
    dev.bus = NULL;
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL_PARAM, sensor_read_temperature_celsius_x100(&dev, &temperature));
    dev.bus = &invalid;
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL_PARAM, sensor_read_temperature_celsius_x100(&dev, &temperature));
    invalid = bus;
    invalid.read = NULL;
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL_PARAM, sensor_read_temperature_celsius_x100(&dev, &temperature));
    TEST_ASSERT_EQUAL_INT(1234, temperature);
}

void test_all_bus_failure_statuses_are_propagated(void) {
    const i2c_status_t failures[] = {I2C_STATUS_ERROR_NACK, I2C_STATUS_ERROR_TIMEOUT, I2C_STATUS_ERROR_BUS_BUSY};
    for (size_t i = 0; i < sizeof(failures) / sizeof(failures[0]); ++i) {
        failure_status = failures[i];
        fail_next_read = true;
        TEST_ASSERT_EQUAL(SENSOR_ERR_COMM_FAIL, sensor_init(&dev, &bus));
        TEST_ASSERT_FALSE(dev.is_initialized);
        fail_next_write = true;
        TEST_ASSERT_EQUAL(SENSOR_ERR_COMM_FAIL, sensor_init(&dev, &bus));
        TEST_ASSERT_FALSE(dev.is_initialized);
        TEST_ASSERT_EQUAL(SENSOR_OK, sensor_init(&dev, &bus));
        fail_next_read = true;
        int16_t temperature = 1234;
        TEST_ASSERT_EQUAL(SENSOR_ERR_COMM_FAIL, sensor_read_temperature_celsius_x100(&dev, &temperature));
    }
}

void test_failed_reinitialization_invalidates_previous_device(void) {
    int16_t temperature = 1234;
    for (uint8_t scenario = 0; scenario < 6; ++scenario) {
        i2c_bus_t invalid = bus;
        mock_regs[SENSOR_REG_WHO_AM_I] = SENSOR_EXPECTED_CHIP_ID;
        TEST_ASSERT_EQUAL(SENSOR_OK, sensor_init(&dev, &bus));
        sensor_status_t expected = SENSOR_ERR_COMM_FAIL;
        if (scenario == 0) fail_next_read = true;
        if (scenario == 1) fail_next_write = true;
        if (scenario == 2) {
            mock_regs[SENSOR_REG_WHO_AM_I] = 0;
            expected = SENSOR_ERR_INVALID_ID;
        }
        if (scenario == 3) invalid.read = NULL;
        if (scenario == 4) invalid.write = NULL;
        if (scenario >= 3) expected = SENSOR_ERR_NULL_PARAM;
        TEST_ASSERT_EQUAL(expected, sensor_init(&dev, scenario == 5 ? NULL : &invalid));
        TEST_ASSERT_FALSE(dev.is_initialized);
        TEST_ASSERT_NULL(dev.bus);
        TEST_ASSERT_EQUAL(SENSOR_ERR_COMM_FAIL, sensor_read_temperature_celsius_x100(&dev, &temperature));
    }
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_successful_init);
    RUN_TEST(test_init_invalid_chip_id);
    RUN_TEST(test_init_i2c_bus_error);
    RUN_TEST(test_read_positive_temperature);
    RUN_TEST(test_read_negative_temperature);
    RUN_TEST(test_read_before_init_fails);
    RUN_TEST(test_null_params_safety);
    RUN_TEST(test_temperature_range_and_fractional_values);
    RUN_TEST(test_missing_bus_and_callbacks);
    RUN_TEST(test_all_bus_failure_statuses_are_propagated);
    RUN_TEST(test_failed_reinitialization_invalidates_previous_device);
    return UNITY_END();
}
