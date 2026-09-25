# Data Analysis for Educational Optical Coherence Tomography Kit | Thorlabs EDU-OCT1(/M)
This folder contains python code used for processing the raw data created by the software of the [EDU-OCT1(/M) Educational Optical Coherence Tomography Kit](https://www.thorlabs.com/f1124453). This code is not necessary to obtain OCT images with the kit, but serves as an additional educational resource for more data-focused users, as well as a starting point for modifications to the data processing. 
This readme assumes that the Theory and Implementation chapters of the [EDU-OCT1(/M) Manual](https://www.thorlabs.com/api/thorlabs-products/support-documents?productId=EDU-OCT1&fileName=DOC-105021.pdf) have been read and focusses on the description of the python code. 

## Requirements 
The code is contained in .py files that can be run as script using a python interpreter of version 3.9 or later. They make use of the python packages *numpy, scipy* and *skimage*.

## SpectralDomainOCT_RawDataProcessing_2D.py
This script processes raw data from the Spectral Domain 2D mode. It can be used to see the effect of wavelength sampling on the OCT result. 

**Input** (to be entered within the .py file):
 - Path to the 2D SD raw data file (_raw.btf) 
 - Path to the wavelength <-> pixel map, which can be saved in the calibration window
 - Output path

**Options** (to be entered within the .py file):
 - Choose between linear, logarithmic and optimized output representation by changing the variable _out_type_ to "lin", "log", or "opt".
    - For optimized representation, the variable _optimize_value_ should be adjusted to a numerical value that leads to the desired effect. A larger value lead to a brighter image.
 - Choose if the number of pixels (i.e. wavelength sampling points) should be halved by changing the variable _reduce_number_of_pixels_ to _True_ or _False_. 

**Output**:
 - SD OCT B-Scan as 8-bit tif in linear, logarithmic, or optimized representation

### Calculation Details
First, the raw data and wavelength to pixel mapping are loaded. 

If the variable _reduce_number_of_pixels_ is set to _True_ the number of pixels, i.e. wavelength sampling points, are halved by averaging adjacent pixels pairwise. This simulates a spectrometer camera with half as many pixels. 

An equidistant wavenumber grid is created and the data is linearly interpolated onto this grid.

Afterwards, an inverse FFT is performed on the data, which is the main processing step to obtain the OCT result. Because the input data are real numbers, the FFT result is mirror symmetric and half of the result can be safely discarded. The OCT result is the absolute value of the inverse FFT. 

After rotating the result image to match the convention of the EDU-OCT software, it is saved as an 8-bit tif file in linear, logarithmic, or optimized representation. For linear and optimized there are additional variables to change the way the result looks. These can be useful for highlighting weak features. 


## SpectralDomainOCT_RawDataProcessing_3D.py
This script processes raw data from the Spectral Domain 3D mode.

**Input** (to be entered within the .py file):
 - Path to the 16-bit 3D SD raw data file (.btf.Raw_s0c0.tid) 
 - Path to the wavelength <-> pixel map, which can be saved in the calibration window
 - Output path

**Options** (to be entered within the .py file):
 - Choose between linear, logarithmic and optimized output representation by changing the variable _out_type_ to "lin", "log", or "opt".
    - For optimized representation, the variable _optimize_value_ should be adjusted to a numerical value that leads to the desired effect. A larger value lead to a brighter image.

**Output**:
 - 3D SD OCT result as 8-bit tif in linear, logarithmic, or optimized representation. Each image of the stack is an _en-face_ image of the sample at a certain depth. 

### Calculation Details
First, the raw data and wavelength to pixel mapping are loaded. 

An equidistant wavenumber grid is created. An empty array is created which will be filled with the OCT result. 

In the input raw data stack, each image corresponds to one stage position and has a wavelength axis and a spatial axis. Each input image is processed to a B-Scan by interpolating to the equidistant wavenumber grid and then performing an inverse FFT along the wavelength/wavenumber axis. Because the input data are real numbers, the FFT result is mirror symmetric and half of the result can be safely discarded. The OCT result is the absolute value of the inverse FFT. 

After looping through all input images we get a stack of B-Scans, which is then converted to an en-face view to match the EDU-OCT software convention. The result is saved as an 8-bit tif stack in linear, logarithmic, or optimized representation. For optimized there is an additional variable to change the way the result looks. This can be useful for highlighting weak features. 


## SweptSourceOCT_RawDataProcessing_3D.py
This script processes raw data from the Swept Source mode.

**Input** (to be entered within the .py file):
 - Path to the 16-bit 3D SS raw data file (.btf.Raw_s0c0.tid) 
 - Path to the (automatically saved) .xml file which contains the measurement parameters
 - Output path

**Options** (to be entered within the .py file):
 - Choose between linear, logarithmic and optimized output representation by changing the variable _out_type_ to "lin", "log", or "opt".
    - For optimized representation, the variable _optimize_value_ should be adjusted to a numerical value that leads to the desired effect. A larger value lead to a brighter image.

**Output**:
 - 3D SS OCT result as 8-bit tif in linear, logarithmic, or optimized representation. Each image of the stack is an _en-face_ image of the sample at a certain depth. 

### Calculation Details
First, the raw data and xml file are loaded. The angles needed for calculating the wavelength corresponding to each input image are extracted from the xml file. The wavelength is calculated with the generalized grating equation.

An equidistant wavenumber grid is created. 

To obtain the OCT result the data needs to be interpolated onto the equidistant wavenumber grid and inverse Fourier transformed. Since the raw input data is quite large (e.g. 1280x1024x1000) this processing step is performed in chunks (e.g. 400x400x1000) to keep within the RAM. Because the input data are real numbers, the FFT result is mirror symmetric and half of the result can be safely discarded. The OCT result is the absolute value of the inverse FFT. 

The result is saved as an 8-bit tif stack in linear, logarithmic, or optimized representation. For optimized there is an additional variable to change the way the result looks. This can be useful for highlighting weak features. 


## TimeDomainOCT_RawDataProcessing_3D.py
This script processes raw data from the Time Domain mode.

**Input** (to be entered within the .py file):
 - Path to the 16-bit 3D TD raw data file (.btf.Raw_s0c0.tid) 
 - Output path

**Options** (to be entered within the .py file):
 - Choose between linear, logarithmic and optimized output representation by changing the variable _out_type_ to "lin", "log", or "opt".
    - For optimized representation, the variable _optimize_value_ should be adjusted to a numerical value that leads to the desired effect. A larger value lead to a brighter image.

**Output**:
 - 3D TD OCT result as 8-bit tif in linear, logarithmic, or optimized representation. Each image of the stack is an _en-face_ image of the sample at a certain depth. 

### Calculation Details
The raw data is loaded and converted to float to avoid unsigned integer wraparound when subtracting images. 

To obtain the OCT result, a 5-step method is used [^Larkin1996]. This takes 5 consecutive images and calculates one OCT result image from them. The script loops over the whole input data 5 images at a time. Afterwards, non-physical negative values are set to zero and the square root is taken to complete the processing.  

The result is saved as an 8-bit tif stack in linear, logarithmic, or optimized representation. For optimized there is an additional variable to change the way the result looks. This can be useful for highlighting weak features. 

# References To Literature
[^Larkin1996] Kieran G. Larkin, "Efficient nonlinear algorithm for envelope detection in white light interferometry," J. Opt. Soc. Am. A 13, 832-843 (1996), https://doi.org/10.1364/JOSAA.13.000832