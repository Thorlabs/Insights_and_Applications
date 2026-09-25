import math
import xml.etree.ElementTree as ET

import numpy as np
from scipy import fft
from scipy.interpolate import interp1d
from skimage import io

"""
This script takes Raw data created by the EDU-OCT software in Swept-Source mode and outputs
the OCT result as a 8-bit tif file. 
Necessary measurement parameters are taken from the xml file associated with the measurement.
"""

# Load raw image
image_path = "SS_Test.btf.Raw_R1_s0c0.tif"
image = io.imread(image_path, plugin='tifffile').astype(np.float32)

# Set output filename and choose between linear, logarithmic and optimized representation
save_path = "SS_out.tif"
out_type = "log"  # 'lin', 'log', 'opt'

# Get measurement parameters from the xml file
xml_path = image_path.split("btf")[0] + "xml"
tree = ET.parse(xml_path)
root = tree.getroot()

params = {}
for element in root.iter():
    params[element.tag] = element.attrib

ss_oct = root.find("SS_OCT")

L = image.shape[0]  # Number of images, i.e. number of wavelength samples
gamma_start = np.deg2rad(
    float(ss_oct.get("GammaStart"))
)  # Angle where the measurement starts (red light exits the exit slit)
gamma_end = np.deg2rad(float(ss_oct.get("GammaEnd")))
gamma_cal = np.deg2rad(
    float(ss_oct.get("GammaCal"))
)  # Half of the setup angle theta. At gamma_cal the stage is rotated so that 0 order light falls into the exit slit

v = (gamma_end - gamma_start) / L  #  Angle (in rad) per frame
d = 1.0 / (2400 * 10**3)  # Line spacing of the grating

# Calculate wavelength and wavenumber belonging to every image
wl = d * (
    np.sin(-gamma_start - np.arange(0, L) * v)
    + np.sin(2 * gamma_cal - gamma_start - np.arange(0, L) * v)
)  # Calculate wavelengths for all angles
k = 2 * np.pi / wl  # Calculate wavenumbers for all angles
eq_k = np.linspace(k[0], k[-1], num=L)  # Equidistant k grid


# Perform iFFT
# Process the iFFT in chunks, to limit RAM consumption
max1 = 400  # Adjust according to your RAM, for 16 GB RAM 400x400 works well
max2 = 400

i_range = range(math.ceil(image.shape[1] / max1))
j_range = range(math.ceil(image.shape[2] / max2))

L2 = math.floor(
    L / 2
)  # Half of the Fourier transform result suffices because of symmetry

for i in i_range:
    for j in j_range:
        image2 = image[:, i * max1 : (i + 1) * max1, j * max2 : (j + 1) * max2]
        # Interpolate to equidistant k grid
        interp_func = interp1d(k, image2, axis=0)
        interp_data = interp_func(eq_k)
        # Inverse Fourier transform
        ifft = fft.ifft(interp_data, axis=0)
        ifft = ifft[: L2]
        ifft = np.abs(ifft)
        ifft = ifft.astype(np.uint16)

        if j == 0:
            ifft_x = ifft
        else:
            ifft_x = np.dstack((ifft_x, ifft))

    if i == 0:
        ifft_xy = ifft_x
    else:
        ifft_xy = np.hstack((ifft_xy, ifft_x))

# Save as 8-bit tif file
if out_type == "lin":
    img8 = (ifft_xy / np.max(ifft_xy) * 255).astype(np.uint8)
if out_type == "log":
    img8 = (np.log10(ifft_xy + 1) / np.log10(np.max(ifft_xy) + 1) * 255).astype(
        np.uint8
    )
if out_type == "opt":
    optimize_value = 255
    I_opt = ifft_xy / np.max(ifft_xy) * optimize_value
    img8 = (np.log10(I_opt + 1) / np.log10(np.max(I_opt) + 1) * 255).astype(np.uint8)

io.imsave(save_path, img8)