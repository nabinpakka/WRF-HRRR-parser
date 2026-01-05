class BitReader:
    def __init__(self, data: bytes, initial_bit_offset: int = 0):
        self.data = data
        self.byte = 0  # Current byte being processed
        self.offset = initial_bit_offset % 8
        self.byte_index = initial_bit_offset // 8

        if self.byte_index < len(self.data):
            self.byte = self.data[self.byte_index]
            
    def reset_offset(self):
        """Reset the bit cursor to the beginning of the next byte."""
        self.offset = 0

    def read_bit(self):
        """Reads a single bit from the current position in the stream."""
        if self.offset == 8 or self.offset == 0:  # If we are at a byte boundary
            if self.byte_index >= len(self.data):
                raise EOFError("Reached the end of the data.")
            self.byte = self.data[self.byte_index]  # Read the next byte
            self.byte_index += 1
            self.offset = 0  # Reset bit offset to 0 (start of byte)
        
        # Extract the current bit
        bit = (self.byte >> (7 - self.offset)) & 0x01  # Get the bit at position 7-offset
        self.offset += 1  # Move to the next bit in the byte
        return bit

    def read_uint(self, nbits):
        """Reads an unsigned integer encoded over `nbits` bits."""
        result = 0
        for i in range(nbits - 1, -1, -1):
            bit = self.read_bit()
            result |= bit << i  # Shift the bit into the correct position
        return result

    def read_int(self, nbits):
        """Reads a signed integer encoded over `nbits` bits."""
        result = 0
        negative = 1
        for i in range(nbits - 1, -1, -1):
            bit = self.read_bit()
            if i == (nbits - 1) and bit == 1:  # First bit indicates a negative number
                negative = -1
            else:
                result |= bit << i
        return negative * result

    def read_uints_block(self, bits, count, reset_offset=False):
        """Reads a set of unsigned integers encoded over `bits` bits."""
        if reset_offset:
            self.reset_offset()

        if bits == 0:
            return []
        
        result = [0] * count
        for i in range(count):
            result[i] = self.read_uint(bits)
        
        return result
