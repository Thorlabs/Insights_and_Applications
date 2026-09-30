import math

import numpy as np
import scipy
from skimage import io

"""
This script takes 3D Raw data created by the EDU-OCT software in Spectral-Domain mode and outputs
the OCT result as a 8-bit tif file. 
A list of the wavelength to pixel mapping must be provided, which can be saved in the calibration window. 
"""

image_path = "SD_Test.btf.Raw_s0c0.tid"  # Raw 3D result file
wavelength_pixel_path = "SD_wavelength.csv"  # List which wavelength belongs to which pixel. This can be saved in the calibration window.

# Set output filename and choose between linear, logarithmic and optimized representation
save_path = "SD_3D_enface.tif"
out_type = "log"  # 'lin', 'log', 'opt'

# Read raw image and wavelength list
image = io.imread(image_path, plugin="tifffile")
nr_lateral_pos = image.shape[0]  # number of lateral positions that were sampled

wl = np.genfromtxt(
    wavelength_pixel_path, skip_header=1, delimiter=","
)  # Load list which wavelength belongs to which pixel
wl = wl[:, 1] * 1e-9
k = 2 * np.pi / wl  # Convert to wavenumbers

L = len(k)
eq_k = np.linspace(k[0], k[-1], num=L)  # Equidistant wavenumber grid

L2 = math.floor(
    L / 2
)  # Only half of the FFT result is relevant, the other half is a mirror image

ifft3D = np.empty((nr_lateral_pos, L2, image.shape[1])) # Allocate memory. This will be filled with a stack of B-Scans.

for i in range(nr_lateral_pos):
    image2D = image[i]
    f = scipy.interpolate.interp1d(k, image2D, axis=1, kind="linear")
    interp_data = f(eq_k)

    # Calculate OCT result with iFFT
    ifft = scipy.fft.ifft(interp_data, axis=1)
    ifft = ifft[:, :L2]
    ifft = np.abs(ifft)

    # Rotate to the usual B-Scan orientation
    ifft = np.rot90(ifft, 3)

    # Write to 3D array
    ifft3D[i] = ifft

# Convert to en-face view. If you want a stack of B-Scans instead, comment out this part.
ifft3D = np.transpose(ifft3D, (1, 2, 0))
ifft3D = np.flip(ifft3D, axis=1)

# Save as 8-bit tif file
if out_type == "lin":
    img8 = (ifft3D / np.max(ifft3D) * 255).astype(np.uint8)
if out_type == "log":
    img8 = (np.log10(ifft3D + 1) / np.log10(np.max(ifft3D) + 1) * 255).astype(np.uint8)
if out_type == "opt":
    optimize_value = 255
    I_opt = ifft3D / np.max(ifft3D) * optimize_value
    img8 = (np.log10(I_opt + 1) / np.log10(np.max(I_opt) + 1) * 255).astype(np.uint8)

io.imsave(save_path, img8)  # Saves pixelmap to tif file