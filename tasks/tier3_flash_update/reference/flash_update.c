/* AIBENCHMARK_ESW_CANARY_V1_tier3_flash_update */
#include "flash_update.h"

static uint16_t crc_extend(uint16_t crc, const uint8_t *data, size_t length) {
    for (size_t i = 0; i < length; ++i) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (uint8_t bit = 0; bit < 8; ++bit) {
            crc = (uint16_t)((crc & 0x8000U) != 0 ? (crc << 1) ^ 0x1021U : crc << 1);
        }
    }
    return crc;
}

uint16_t flash_update_crc(const uint8_t *data, size_t length) {
    if (data == NULL && length != 0) return 0;
    return crc_extend(0xFFFF, data, length);
}

bool flash_update_begin(flash_update_t *u, const update_hal_t *hal, uint8_t active_slot, const uint8_t *data, size_t length) {
    if (u == NULL) return false;
    u->initialized = false;
    if (hal == NULL || hal->erase == NULL || hal->write == NULL || hal->read == NULL || hal->commit == NULL ||
        active_slot > 1U || data == NULL || length == 0 || length > 256U) return false;
    u->hal = *hal; u->data = data; u->length = length; u->offset = 0;
    u->target = (uint8_t)(1U - active_slot);
    u->crc = flash_update_crc(data, length); u->verified = 0xFFFF;
    u->state = UPDATE_ERASE; u->initialized = true;
    return true;
}

int flash_update_step(flash_update_t *u) {
    if (u == NULL || !u->initialized) return UPDATE_ARGUMENT;
    if (u->state == UPDATE_DONE) return UPDATE_OK;
    if (u->state == UPDATE_ERROR) return UPDATE_IO;
    int rc = -1;
    if (u->state == UPDATE_ERASE) {
        rc = u->hal.erase(u->hal.ctx, u->target);
        if (rc == 0) u->state = UPDATE_WRITE;
    } else if (u->state == UPDATE_WRITE) {
        size_t chunk = u->length - u->offset;
        if (chunk > 64U) chunk = 64U;
        rc = u->hal.write(u->hal.ctx, u->target, u->offset, u->data + u->offset, chunk);
        if (rc == 0) {
            u->offset += chunk;
            if (u->offset == u->length) { u->offset = 0; u->state = UPDATE_VERIFY; }
        }
    } else if (u->state == UPDATE_VERIFY) {
        uint8_t buffer[64];
        size_t chunk = u->length - u->offset;
        if (chunk > 64U) chunk = 64U;
        rc = u->hal.read(u->hal.ctx, u->target, u->offset, buffer, chunk);
        if (rc == 0) {
            u->verified = crc_extend(u->verified, buffer, chunk);
            u->offset += chunk;
            if (u->offset == u->length) {
                if (u->verified != u->crc) { u->state = UPDATE_ERROR; return UPDATE_CRC; }
                u->state = UPDATE_COMMIT;
            }
        }
    } else if (u->state == UPDATE_COMMIT) {
        rc = u->hal.commit(u->hal.ctx, u->target, u->crc, u->length);
        if (rc == 0) u->state = UPDATE_DONE;
    }
    if (rc != 0) { u->state = UPDATE_ERROR; return UPDATE_IO; }
    return UPDATE_OK;
}
