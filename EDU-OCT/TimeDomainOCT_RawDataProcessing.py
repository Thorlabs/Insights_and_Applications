import numpy as np
from skimage import io

"""
This script takes Raw data created by the EDU-OCT software in Time-Domain mode and outputs
the OCT result as a 8-bit tif file. 

Source for 5-step method: 
Larkin 1996 „Efficient nonlinear algorithm for envelope detection in white light interferometry“ https://doi.org/10.1364/JOSAA.13.000832
"""

# Set input file name
image_path = "TD_Test.btf.Raw_s0c0.tid"

# Set output file name and choose between linear, logarithmic and optimized representation
save_path = "TD_out.tif"
out_type = "log"  # 'lin', 'log', 'opt'

# Load raw image
image = io.imread(image_path)
image = image.astype(
    np.float32
)  # Convert from uint16 to float to avoid unsigned integer wraparound (e.g., negative differences).

# Apply 5-step method
i = 0
while i <= image.shape[0] - 4:
    if i == 0:
        image_five_step_squared = np.array(
            [
                (image[i + 1] - image[i + 3]) ** 2
                - (image[i] - image[i + 2]) * (image[i + 2] - image[i + 4])
            ]
        )
    else:
        image_five_step_squared = np.vstack(
            [
                image_five_step_squared,
                np.array(
                    [
                        (image[i + 1] - image[i + 3]) ** 2
                        - (image[i] - image[i + 2]) * (image[i + 2] - image[i + 4])
                    ]
                ),
            ]
        )
    i += 5

image_five_step_squared[image_five_step_squared < 0] = 0  # Remove negative values
result_image = np.sqrt(image_five_step_squared)

# Save as 8-bit tif file
if out_type == "lin":
    img8 = (result_image / np.max(result_image) * 255).astype(np.uint8)
if out_type == "log":
    img8 = (
        np.log10(result_image + 1) / np.log10(np.max(result_image) + 1) * 255
    ).astype(np.uint8)
if out_type == "opt":
    optimize_value = 255
    I_opt = result_image / np.max(result_image) * optimize_value
    img8 = (np.log10(I_opt + 1) / np.log10(np.max(I_opt) + 1) * 255).astype(np.uint8)

io.imsave(save_path, img8)
