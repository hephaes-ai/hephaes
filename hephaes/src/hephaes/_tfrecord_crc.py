from __future__ import annotations

_CRC32C_POLYNOMIAL = 0x82F63B78
_CRC32C_TABLE: tuple[int, ...] = ()


def _build_crc32c_table() -> tuple[int, ...]:
    table: list[int] = []
    for idx in range(256):
        crc = idx
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ _CRC32C_POLYNOMIAL
            else:
                crc >>= 1
        table.append(crc & 0xFFFFFFFF)
    return tuple(table)


def _crc32c(data: bytes) -> int:
    global _CRC32C_TABLE
    if not _CRC32C_TABLE:
        _CRC32C_TABLE = _build_crc32c_table()

    crc = 0xFFFFFFFF
    for byte in data:
        crc = _CRC32C_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return (~crc) & 0xFFFFFFFF


def _masked_crc32c(data: bytes) -> int:
    crc = _crc32c(data)
    return (((crc >> 15) | ((crc << 17) & 0xFFFFFFFF)) + 0xA282EAD8) & 0xFFFFFFFF
