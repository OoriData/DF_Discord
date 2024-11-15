# SPDX-FileCopyrightText: 2023-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
# dflib.datastruct
'''
Common data structure definitions, e.g. for packed data transport
'''
TERRAIN_FORMAT = "!BBBBH"  # network byte order (!), 4 bytes + 1 short
SETTLEMENT_HEADER_FORMAT = "!36s100sBBBB"  # uuid(36), name(100), type(1), imports(1), exports(1), vendor_count(1)
VENDOR_HEADER_FORMAT = "!36s100sIHHHHH"  # uuid(36), name(100), money(4), resources(2x3), inventory_counts(2)
CARGO_HEADER_FORMAT = "!36s100sIHHfffBBBHH"  # uuid(36), name(100), quantity(4), volume(2), weight(2), 3xfloat, 3xbyte, 2xshort
# VEHICLE_HEADER_FORMAT = "!36s100sffHHHHHHHIIH"  # uuid(36), name(100), wear(4), fuel_eff(4), followed by shorts, 1 int, 1 short
VEHICLE_HEADER_FORMAT = "!36s100sfHHHIIiHHI36s36s"  # uuid(36), name(100), wear(4), fuel_eff(4), followed by shorts, 1 int, 1 short
