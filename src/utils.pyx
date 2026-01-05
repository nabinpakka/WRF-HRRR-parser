import numpy as np
cimport numpy as np
cimport cython
from libc.math cimport pow

@cython.boundscheck(False)  # Disable bounds checking for better performance
@cython.wraparound(False)   # Disable negative index handling for better performance
def undo_second_order_differencing(np.ndarray[double, ndim=1] packed_values, tuple first_values):
    cdef int i, n = packed_values.shape[0]
    cdef double h1, h2, hmin, hn, fn1, fn2
    cdef double* packed_ptr  # Pointer to the packed values
    cdef double* original_ptr  # Pointer to the original values
    cdef np.ndarray[double, ndim=1] original_values = np.empty(n, dtype=np.float64)

    # Unpack first values
    h1, h2, hmin = first_values

    # Get pointers to the NumPy arrays
    packed_ptr = <double*> packed_values.data
    original_ptr = <double*> original_values.data

    # Initialize the first two elements
    original_ptr[0] = h1
    original_ptr[1] = h2

    # Loop through and undo second-order differencing
    for i in range(2, n):
        hn = packed_ptr[i]
        fn1 = original_ptr[i - 1]
        fn2 = original_ptr[i - 2]
        original_ptr[i] = hn + (2 * fn1) - fn2 + hmin

    return original_values


@cython.boundscheck(False)  # Disable bounds checking for speedup
@cython.wraparound(False)   # Disable negative index handling for speedup
def unscale_values(np.ndarray[np.float64_t, ndim=1] values, int binary_scale_factor, int decimal_scale_factor, double reference_value) -> np.ndarray:
    """
    Scale the values based on the binary and decimal scale factors and the reference value.
    """
    cdef double scale
    cdef int i
    cdef int n = values.shape[0]  # Number of elements in the array

    # Calculate the scale factor
    scale = pow(2, binary_scale_factor) * pow(10, -decimal_scale_factor)

    # Pre-allocate the output array
    cdef np.ndarray[np.float64_t, ndim=1] scaled_values = np.empty(n, dtype=np.float64)

    # Perform scaling
    for i in range(n):
        scaled_values[i] = reference_value + values[i] * scale

    return scaled_values

