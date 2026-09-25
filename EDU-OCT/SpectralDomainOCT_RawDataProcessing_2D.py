import math
import scipy
import numpy as np 
from skimage import io

'''
This script takes 2D Raw data created by the EDU-OCT software in Spectral-Domain mode and outputs
the OCT result as a 8-bit image file. 
A list of the wavelength to pixel mapping must be provided, which can be saved in the calibration window. 
The option to virtually halve the number of camera pixels (in the wavelength dimension) is included to see the influence of wavelength sampling. 

'''

image_path = 'SD_2D_raw.btf'   # Raw 2D result file
wavelength_pixel_path = 'SD_wavelength.csv' # List which wavelength belongs to which pixel. This can be saved in the calibration window. 
reduce_number_of_pixels = False    # If True, the number of pixels is halved

# Set output filename and choose between linear, logarithmic and optimized representation
save_path = "SD_2D_out.png"
out_type = "log"  # 'lin', 'log', 'opt'

# Read raw image and wavelength list
image = io.imread(image_path)

wl = np.genfromtxt(wavelength_pixel_path,skip_header=1, delimiter=',')  # Load list which wavelength belongs to which pixel
wl = wl[:,1]*1e-9 
k = 2*np.pi/wl # Convert to wavenumbers

# Reduce number of pixels, if selected
if reduce_number_of_pixels:
    k = 0.5*(k[0::2] + k[1::2]) # Averages adjacent pixels pairwise
    image = 0.5*(image[:,0::2] + image[:,1::2]) # Averages adjacent pixels pairwise

# Interpolate to equidistant wavenumber grid
L = len(k)
step = (k[-1]-k[0])/(L-1)  
eq_k = np.linspace(k[0],k[-1],num=int((k[-1]-k[0])/step))   # Equidistant wavenumber grid

f = scipy.interpolate.interp1d(k, image, axis=1, kind='linear')
interp_data= f(eq_k)

# Calculate OCT result with iFFT
ifft = scipy.fft.ifft(interp_data, axis=1)

L = ifft.shape[1]
L2 = math.floor(L/2) # Only half of the FFT result is relevant, the other half is a mirror image
ifft = ifft[:,:L2]
ifft = np.abs(ifft)

# Rotate to the usual B-Scan orientation
ifft = np.rot90(ifft)
ifft = np.rot90(ifft)
ifft = np.rot90(ifft)

# Save as 8-bit image, e.g. png
if out_type == "lin":
    vmax = 1.5 # For adjusting contrast, to save without contrast adjustment, change the value to np.max(ifft)
    ifft_clipped = np.clip(ifft, 0, vmax)
    ifft_scaled = (ifft_clipped / vmax *255).astype(np.uint8)

if out_type == "log":
    ifft_scaled = (np.log10(ifft + 1) / np.log10(np.max(ifft) + 1) * 255).astype(
        np.uint8
    )
if out_type == "opt":
    optimize_value = 255
    I_opt = ifft / np.max(ifft) * optimize_value
    ifft_scaled = (np.log10(I_opt + 1) / np.log10(np.max(I_opt) + 1) * 255).astype(np.uint8)

io.imsave(save_path, ifft_scaled)    # Saves pixelmap to e.g. png