# cython: boundscheck=False, wraparound=False, cdivision=True
cdef class BitReader:
    cdef unsigned char* data_ptr  # Pointer to the data
    cdef int byte  # Current byte being processed
    cdef int offset  # Bit offset within the current byte
    cdef int byte_index  # Index of the current byte in the data
    cdef Py_ssize_t data_len  # Length of the data (as size_t for pointer arithmetic)
    
    def __init__(self, bytes data, int initial_bit_offset=0):
        self.data_ptr = <unsigned char*>data  # Cast bytes to unsigned char* pointer
        self.data_len = len(data)
        self.offset = initial_bit_offset % 8
        self.byte_index = initial_bit_offset // 8

        if self.byte_index < self.data_len:
            self.byte = self.data_ptr[self.byte_index]
        else:
            self.byte = 0
    
    cpdef void reset_offset(self):
        """Reset the bit cursor to the beginning of the next byte."""
        self.offset = 0
    
    cdef inline int read_bit(self):
        """Reads a single bit from the current position in the stream."""
        if self.offset == 8 or self.offset == 0:  # If we are at a byte boundary
            if self.byte_index >= self.data_len:
                raise EOFError("Reached the end of the data.")
            self.byte = self.data_ptr[self.byte_index]  # Read the next byte
            self.byte_index += 1
            self.offset = 0  # Reset bit offset to 0 (start of byte)
        
        # Extract the current bit
        bit = (self.byte >> (7 - self.offset)) & 0x01  # Get the bit at position 7-offset
        self.offset += 1  # Move to the next bit in the byte
        return bit
    
    cpdef int read_uint(self, int nbits):
        """Reads an unsigned integer encoded over `nbits` bits."""
        cdef int result = 0
        cdef int bit
        for i in range(nbits - 1, -1, -1):
            bit = self.read_bit()
            result |= bit << i  # Shift the bit into the correct position
        return result

    cpdef int read_int(self, int nbits):
        """Reads a signed integer encoded over `nbits` bits."""
        cdef int result = 0
        cdef int negative = 1
        cdef int bit
        for i in range(nbits - 1, -1, -1):
            bit = self.read_bit()
            if i == (nbits - 1) and bit == 1:  # First bit indicates a negative number
                negative = -1
            else:
                result |= bit << i
        return negative * result

    cpdef list read_uints_block(self, int bits, int count, bint reset_offset=False):
        """Reads a set of unsigned integers encoded over `bits` bits."""
        cdef int i
        cdef list result
        if reset_offset:
            self.reset_offset()

        if bits == 0:
            return []

        result = [0] * count
        for i in range(count):
            result[i] = self.read_uint(bits)

        return result