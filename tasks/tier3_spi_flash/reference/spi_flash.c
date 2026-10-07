/* AIBENCHMARK_ESW_CANARY_V1_tier3_spi_flash */
#include "spi_flash.h"

static int ready(spi_flash_t *d) {
    const uint8_t command = 0x05;
    for (uint32_t i = 0; i < d->poll_limit; ++i) {
        uint8_t status = 0;
        if (d->hal.transaction(d->hal.ctx, &command, 1, &status, 1) != 0) return FLASH_IO;
        if ((status & 1U) == 0) return FLASH_OK;
    }
    return FLASH_TIMEOUT;
}

static int enable(spi_flash_t *d) {
    const uint8_t command = 0x06;
    return d->hal.transaction(d->hal.ctx, &command, 1, NULL, 0) == 0 ? FLASH_OK : FLASH_IO;
}

static void address_bytes(uint8_t *tx, uint32_t address) {
    tx[1] = (uint8_t)(address >> 16);
    tx[2] = (uint8_t)(address >> 8);
    tx[3] = (uint8_t)address;
}

int spi_flash_init(spi_flash_t *d, const spi_hal_t *hal, uint32_t poll_limit, uint8_t jedec[3]) {
    if (d == NULL) return FLASH_ARGUMENT;
    d->initialized = false;
    if (hal == NULL || hal->transaction == NULL || poll_limit == 0 || jedec == NULL) return FLASH_ARGUMENT;
    const uint8_t command = 0x9F;
    uint8_t id[3];
    if (hal->transaction(hal->ctx, &command, 1, id, 3) != 0) return FLASH_IO;
    for (size_t i = 0; i < 3; ++i) jedec[i] = id[i];
    d->hal = *hal;
    d->poll_limit = poll_limit;
    d->initialized = true;
    return FLASH_OK;
}

int spi_flash_program(spi_flash_t *d, uint32_t address, const uint8_t *data, size_t length) {
    if (d == NULL || !d->initialized || address > UINT32_C(0xFFFFFF) ||
        length > UINT32_C(0x1000000) - address || (data == NULL && length != 0)) return FLASH_ARGUMENT;
    while (length != 0) {
        size_t chunk = 256U - (address & 255U);
        if (chunk > length) chunk = length;
        int status = ready(d);
        if (status != FLASH_OK) return status;
        status = enable(d);
        if (status != FLASH_OK) return status;
        uint8_t tx[260];
        tx[0] = 0x02;
        address_bytes(tx, address);
        for (size_t i = 0; i < chunk; ++i) tx[4 + i] = data[i];
        if (d->hal.transaction(d->hal.ctx, tx, chunk + 4U, NULL, 0) != 0) return FLASH_IO;
        status = ready(d);
        if (status != FLASH_OK) return status;
        address += (uint32_t)chunk;
        data += chunk;
        length -= chunk;
    }
    return FLASH_OK;
}

int spi_flash_erase(spi_flash_t *d, uint32_t address) {
    if (d == NULL || !d->initialized || address > UINT32_C(0xFFFFFF) || address % 4096U != 0) return FLASH_ARGUMENT;
    int status = ready(d);
    if (status != FLASH_OK) return status;
    status = enable(d);
    if (status != FLASH_OK) return status;
    uint8_t tx[4] = {0x20, 0, 0, 0};
    address_bytes(tx, address);
    if (d->hal.transaction(d->hal.ctx, tx, 4, NULL, 0) != 0) return FLASH_IO;
    return ready(d);
}
