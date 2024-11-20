# SPDX-FileCopyrightText: 2023-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
# df_discord.datastruct
'''
Common data structure definitions, e.g. for packed data transport

Format codes used:
! - network standardized byte order
B - byte
H - short unsigned int
NNNs - string via fixed number (NNN) of utf-8 bytes
I - long unsigned int
i - unsigned int
f - float

Notes:
* creation_date is omitted throughout, as not meaningful in map rendering

'''
# All start with id(UUID), name(64s), base_desc(512s)
TERRAIN_FORMAT = "!BBBBH"
SETTLEMENT_HEADER_FORMAT = "!36s64s1024sBBBB"  # uuid(36), name(100), type(1), imports(1), exports(1), vendor_count(1)
# money(i), fuel amt(i/price(h), water a(i)/p(h), food a(i)/p(h), repair_price(h), cargo & vehicle inventory(HH)
VENDOR_HEADER_FORMAT = "!36s64s512siihihihhHH"
# id, name, quantity(I), volume(I), weight(I), capacity(f), fuel(f), water(f), food(f), base_price(i),
# delivery_reward(i), distributor(UUID), vehicle & warehouse & vendor ID
CARGO_HEADER_FORMAT = "!36s64s512sIIIffffii36s36s36s36s"  # 3xfloat, 3xbyte, 2xshort
# VEHICLE_HEADER_FORMAT = "!36s100sffHHHHHHHIIH"  # uuid(36), name(100), wear(4), fuel_eff(4), followed by shorts, 1 int, 1 short
# wear(f), base fuel eff & top speed & offroad capab (HHH), base cargo & weight capac (II), towing capacity(i), ap(H), base max ap(H), value(I), vendor_id, warehouse_id
VEHICLE_HEADER_FORMAT = "!36s64s512sfHHHIIiHHI36s36s"
