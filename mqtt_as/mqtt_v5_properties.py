import ustruct as struct


def encode_byte(value):
    # It takes in a byte and returns a byte
    return value


def encode_two_byte_int(value):
    return struct.pack("!H", value)


def encode_four_byte_int(value):
    return struct.pack("!I", value)


def encode_string(value):
    value = value.encode("utf-8")
    return struct.pack("!H", len(value)) + value


def encode_string_pair(value):
    # just get the first key and value
    key, value = list(value.items())[0]
    return encode_string(key) + encode_string(value)


def encode_binary(value):
    return struct.pack("!H", len(value)) + value


def encode_variable_byte_int(value):
    out = bytearray(4)
    i = 0
    for i in range(4):
        b = value & 0x7F
        value >>= 7
        if value > 0:
            b |= 0x80
        out[i] = b
        if value == 0:
            break
    return out[:i + 1]


# This table does not contain all properties (unlike the decode table)
# as not all properties can be sent by the client.
ENCODE_TABLE = {
    0x01: encode_byte,                # Payload Format Indicator
    0x02: encode_four_byte_int,       # Message Expiry Interval
    0x03: encode_string,              # Content Type
    0x08: encode_string,              # Response Topic
    0x09: encode_binary,              # Correlation Data
    0x0B: encode_variable_byte_int,   # Subscription Identifier
    0x11: encode_four_byte_int,       # Session Expiry Interval
    0x15: encode_string,              # Authentication Method
    0x16: encode_binary,              # Authentication Data
    0x17: encode_byte,                # Request Problem Information
    0x18: encode_four_byte_int,       # Will Delay Interval
    0x19: encode_byte,                # Request Response Information
    0x1C: encode_string,              # Server Reference
    0x1F: encode_string,              # Reason String
    0x21: encode_two_byte_int,        # Receive Maximum
    0x22: encode_two_byte_int,        # Topic Alias Maximum
    0x23: encode_two_byte_int,        # Topic Alias
    0x26: encode_string_pair,         # User Property
    0x27: encode_four_byte_int,       # Maximum Packet Size
}


# MQTT_base class. Handles MQTT protocol on the basis of a good connection.
# Exceptions from connectivity failures are handled by MQTTClient subclass.
def encode_properties(properties: dict):
    # If properties are empty or None, we can just return a single byte (0)
    if properties in (None, {}):
        return bytes(1)

    # We can't modify the properties dict, as user might want to use it later
    # So we will create a new dict with the encoded values.
    # This causes a slight increase in memory usage. But this is acceptable.
    pre_encoded_properties = {}

    # We keep track of the length of the properties
    properties_length = 0

    # Preprocess properties to encode everything as bytes.
    for key, value in properties.items():
        encode_func = ENCODE_TABLE.get(key)
        if encode_func is None:
            # We can just leave that data as is and assume that it is valid.
            tmp_value = value
        else:
            tmp_value = encode_func(value)
        pre_encoded_properties[key] = tmp_value

        # Pre-calculate the length of the properties
        properties_length += 1  # key
        properties_length += len(tmp_value)

    # Mark properties as deleted
    del properties

    variable_length = 1
    if properties_length > 127:
        variable_length += 1
    if properties_length > 16383:
        variable_length += 1
    if properties_length > 2097151:
        variable_length += 1

    # Now we can allocate the byte array
    properties_bytes = bytearray(variable_length + properties_length)
    view = memoryview(properties_bytes)

    i = 0
    while properties_length > 0x7F:
        view[i] = (properties_length & 0x7F) | 0x80
        properties_length >>= 7
        i += 1

    view[i] = properties_length
    i += 1

    for key, value in pre_encoded_properties.items():
        view[i] = key
        i += 1
        view[i:i + len(value)] = value
        i += len(value)

    return properties_bytes


def decode_byte(props, offset):
    value = props[offset]
    offset += 1
    return value, offset


def decode_two_byte_int(props, offset):
    value = struct.unpack_from("!H", props, offset)[0]
    offset += 2
    return value, offset


def decode_four_byte_int(props, offset):
    value = struct.unpack_from("!I", props, offset)[0]
    offset += 4
    return value, offset


def decode_string(props, offset):
    str_length = struct.unpack_from("!H", props, offset)[0]
    offset += 2
    value = props[offset:offset + str_length].decode("utf-8")
    offset += str_length
    return value, offset


def decode_string_pair(props, offset):
    key, offset = decode_string(props, offset)
    value, offset = decode_string(props, offset)
    item = {key: value}
    return item, offset


def decode_binary(props, offset):
    data_length = struct.unpack_from("!H", props, offset)[0]
    offset += 2
    value = props[offset:offset + data_length]
    offset += data_length
    return value, offset


def decode_variable_byte_int(props, offset):
    value = 0
    for i in range(4):
        b = props[offset]
        value |= (b & 0x7F) << (7 * i)
        offset += 1
        if not b & 0x80:
            break
    return value, offset


decode_property_lookup = {
    0x01: decode_byte,                # Payload Format Indicator
    0x02: decode_four_byte_int,       # Message Expiry Interval
    0x03: decode_string,              # Content Type
    0x08: decode_string,              # Response Topic
    0x09: decode_binary,              # Correlation Data
    0x0B: decode_variable_byte_int,   # Subscription Identifier
    0x11: decode_four_byte_int,       # Session Expiry Interval
    0x12: decode_string,              # Assigned Client Identifier
    0x13: decode_two_byte_int,        # Server Keep Alive
    0x15: decode_string,              # Authentication Method
    0x16: decode_binary,              # Authentication Data
    0x17: decode_byte,                # Request Problem Information
    0x18: decode_four_byte_int,       # Will Delay Interval
    0x19: decode_byte,                # Request Response Information
    0x1A: decode_string,              # Response Information
    0x1C: decode_string,              # Server Reference
    0x1F: decode_string,              # Reason String
    0x21: decode_two_byte_int,        # Receive Maximum
    0x22: decode_two_byte_int,        # Topic Alias Maximum
    0x23: decode_two_byte_int,        # Topic Alias
    0x24: decode_byte,                # Maximum QoS
    0x25: decode_byte,                # Retain Available
    0x26: decode_string_pair,         # User Property
    0x27: decode_four_byte_int,       # Maximum Packet Size
    0x28: decode_byte,                # Wildcard Subscription Available
    0x29: decode_byte,                # Subscription Identifiers Available
    0x2A: decode_byte,                # Shared Subscription Available
}


def decode_properties(props, properties_length):
    if isinstance(props, memoryview):
        props = bytes(props)  # If a memoryview is passed, make a copy
    offset = 0
    properties = {}

    while offset < properties_length:
        property_identifier = props[offset]
        offset += 1

        if property_identifier in decode_property_lookup:
            decode_function = decode_property_lookup[property_identifier]
            value, offset = decode_function(props, offset)
            properties[property_identifier] = value
        else:
            raise ValueError(f"Unknown property identifier: {property_identifier}")

    return properties
