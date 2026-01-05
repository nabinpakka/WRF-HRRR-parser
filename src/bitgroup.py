import numpy as np

class BitGroup:
    def __init__(self, reference, width, length):
        self.Reference = reference  # Group reference value
        self.Width = width  # Bit width of values in this group
        self.Length = length  # Number of values in this group

    def zero_group(self):
        """Return a list of zeros with a length equal to the group's length."""
        return [0] * self.Length

    def read_data(self, bit_reader):
        """Read the data for this group using the bit reader."""
        if self.Width != 0:
            # Read Length number of values, each of Width bits
            uint_array = bit_reader.read_uints_block(bits=self.Width, count=self.Length, reset_offset=False)
            uint_array = np.array(uint_array, dtype=np.int64)
            final = uint_array + int(self.Reference)
            return final
        else:
            output = self.zero_group()
            output = np.array(output, dtype=np.int64)
            final = output + int(self.Reference)
            return final
        
    def __repr__(self):
        return f"BitGroupParameter(Reference={self.Reference}, Width={self.Width}, Length={self.Length})"
        

class BitGroupReader:
    def __init__(self, num_groups, num_bits, group_width_bits, group_width, group_length_increment, group_lengths_reference, group_scaled_length_bits, group_last_length):
        self.NG = num_groups
        self.Bits = num_bits
        self.GroupWidthsBits = group_width_bits
        self.GroupWidths = group_width
        self.GroupLengthIncrement = group_length_increment
        self.GroupLengthsReference = group_lengths_reference
        self.GroupScaledLengthsBits = group_scaled_length_bits
        self.GroupLastLength = group_last_length

    def read_groups(self, bit_reader):
        """Read the bit groups using the BitReader."""
        references = np.array(self.extract_group_references(bit_reader))
        widths = np.array(self.extract_group_bit_widths(bit_reader))
        lengths = np.array(self.extract_group_lengths(bit_reader))

        bit_groups = [None] * self.NG
        for i in range(self.NG):
            bit_groups[i] = BitGroup(references[i], widths[i], lengths[i])

        return bit_groups 

    def extract_group_references(self, bit_reader):
        """Extract group references using the BitReader."""
        number_of_groups = self.NG
        return bit_reader.read_uints_block(bits=self.Bits, count=number_of_groups, reset_offset=True)

    def extract_group_bit_widths(self, bit_reader):
        """Extract group bit widths using the BitReader and add the base group width."""
        number_of_groups = self.NG
        widths = bit_reader.read_uints_block(bits=self.GroupWidthsBits, count=number_of_groups, reset_offset=True)
        return [width + self.GroupWidths for width in widths]

    def extract_group_lengths(self, bit_reader):
        """Extract group lengths using the BitReader and adjust using the length increment and reference."""
        number_of_groups = self.NG
        lengths = bit_reader.read_uints_block(bits=self.GroupScaledLengthsBits, count=number_of_groups, reset_offset=True)

        for j in range(number_of_groups):
            lengths[j] = (lengths[j] * self.GroupLengthIncrement) + self.GroupLengthsReference

        # Set the last group's length directly
        lengths[number_of_groups - 1] = self.GroupLastLength
        bit_reader.reset_offset()
        return lengths

    def check_lengths(self, bit_groups, data_points, data_length):
        tot_bit = 0
        tot_len = 0

        # Calculate total bits and lengths
        for param in bit_groups:
            tot_bit += param.Width * param.Length
            tot_len += param.Length

        # Check if the total lengths exceed the data length
        if tot_len > data_points:
            raise ValueError(f"Checksum error: {data_points} - {tot_len}")

        # Check if the total bits exceed the data length in bytes
        if tot_bit // 8 > data_length:
            raise ValueError(f"Checksum error: {data_length} - {tot_bit // 8}")
        
        return True



