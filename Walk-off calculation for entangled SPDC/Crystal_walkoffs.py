"""
This module can be used to calculate temporal and spatial walk-off effects crossed type-I SPDC systems.
Each Crystal in the system is defined by the material, thickness and orientations.
Then the CrystalSystem is composed of these predefined crystals. Walk-off effects can be summarized in plain-text
and matplotlib figures (spatial walk-off).
The half-opening angle of the photon pair cone is not calculated automatically, but must be given as a parameter,
together with the wavelength.
Input/Output angles are intended to be given in degrees, while the module internally uses and stores the angles in
radians. Units are all in SI base units (e.g. meters), unless noted otherwise (e.g. temporal walk-off given in fs).

The basic principle of these calculations follow Ref. [1,3] (given below), with some adaptations:
    - I consider the definition of delta_phi to be correct when calculating spatial walk-off for spatial compensation
      crystals. However, for the SPDC crystal pair, referencing to the ordinary beam should be incorrect (as there is
      no ordinary beam propagating through the full second crystal, but only the extraordinary does exist). Details
      for my change are given in the code below. This is a very strong change, fully reverting the sign of the
      walk-off effect. As this can be to large extend be mitigated by using the spatial compensation plates in a
      mirrored configuration, it is not easy to verify.
    - Take into account path of Poynting vector for beam travel times (not just the plain thickness) for
      temporal walk-off calculation.
    - Take angles of polarizations with optical axis into account, instead of assuming perfectly ordinary beams and
      theta = cut-angle. Furthermore, walk-off effects are calculated explicitly for all crystals in the pair and
      separately for signal and idler.
    - "legacy_mode" levels can be used to discard/ignore the adaptations discussed above.

Generally, it is assumed, that the beam propagation direction can be calculated (approximately) for both signal/idler
and both polarizations from the "detector aperture" position at equal distance to the center of the SPDC crystal pair.
Differences should be considered in case of notably (asymmetric) beam displacement effects or non-degenerate pair
wavelengths.
Furthermore, the crystals here are all birefringent and will change the polarization state of a polarized light ray
passing them, as long as the polarization is not perfectly aligned with the crystal's optical axis (projected to the
plane perpendicular to ray propagation). I.e. each crystal may act like a (many) multi-order waveplates, causing
increased polarization ellipticity and rotation of the polarization axis, up to some slight depolarization of the beam
(finite coherence length!). These effects depend very sensitively on the crystal thickness (on the order of the
wavelength) and are beyond the scope of this script, as the thickness is usually not known with the required precision.

The script has been extended to provide some support for Type-II SPDC systems as well. In this case we assume a perfect
half-waveplate, with its fast axis oriented at 45° with respect to the H & V polarizations, being inserted between the
SPDC crystal and the SCC crystals. This causes the H & V polarizations to swap roles, allowing for compensation with the
SCC crystals having identical cut-angles, but half thickness, as the SPDC crystal.

References to literature:
    - [1] J. B. Altepeter, E. R. Jeffrey, and P. G. Kwiat, "Phase-compensated ultra-bright source of entangled photons",
      Opt. Exp. 13, 8951-8959, (2005)
    - [2a] A. Migdall, "Polarization directions of noncollinear phase-matched optical parametric downcoversion output",
      J. Opt. Soc. Am. B, 14, 1093-1098, (1997);
      Similarly discussed in: [2b] R. Rangarajana, A. B. U’Ren, and P. G. Kwiat,
      "Polarization dependence on downconversion emission angle: investigation of the ‘Migdall effect’",
      Journal of Modern Optics, 58, 312–317, (2011)
    - [3] R. Rangarajan, M. Goggin, and P. G. Kwiat, "Optimizing type-I polarization-entangled photons",
      Opt. Exp. 17, 18920-18933, (2009)

Python requirements:
    - minimum version: 3.9 (for type annotations)
    - 3rd party-packages: numpy, scipy, matplotlib

Written by:
    Florian Bayer (fbayer@thorlabs.com)
    Educational Products
    Thorlabs GmbH
    Münchner Weg 1
    85232 Bergkirchen
    Germany
    www.thorlabs.com
    April 2024
"""

import numpy as np
from scipy.spatial.transform import Rotation as ro
from scipy.constants import c

import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.ticker import AutoMinorLocator

from typing import Union
from warnings import warn
from copy import deepcopy

np.seterr(divide='ignore', invalid='ignore')  # zero incidence angles may cause warnings.

# Set legacy mode levels (less accurate), (un)comment lines to switch off (on):
legacy_mode = []
# Calculate theta angle from beam k-vector direction rather than polarization
# and assume the beam to be fully ordinary for theta angles smaller than legacy_theta_threshold (use with care!):
# legacy_mode.append('theta_calc')
legacy_theta_threshold = 8  # threshold angle (deg) -> smaller theta angles are treated as fully ordinary beams
# Always reference the phi_delta phase to the fully ordinary beam, to be in line with the definition given in Ref. [1]
#legacy_mode.append('phi_delta_ref_to_o')
# Ignore Poynting vector walk-off and incidence-angle dependencies for temporal walk-off
# (just use plain crystal thickness):
#legacy_mode.append('t_walkoff_ign_angles')
# Ignore delta phase contribution to temporal walk-off (ignored automatically, if 't_walkoff_ign_angles' is activated
#legacy_mode.append('t_walkoff_ign_delta')
# Assume that the walk-off is identical for both crystals in the pair, where the photon pairs are generated:
#legacy_mode.append('eq_pair_s_walkoff')  # for spatial walk-off
#legacy_mode.append('eq_pair_t_walkoff')  # for temporal walk-off
# Don't redefine polarization vectors for created photon pairs according to the Migdall effect [2]. Instead, keep the
# polarization vectors defined by the user or the default nominal polarizations. Note that the Migdal effect produces
# quite notable asymmetry (around the pump beam) in the polarizations of the beams, even though the crystal axes are
# aligned with high symmetry.
# legacy_mode.append('no_pair-pol_refinement')

# switch off all legacy mode settings:
#legacy_mode = []

if legacy_mode:
    print('LEGACY MODES activated:')
    print(legacy_mode)

# directions (names as seen along pump direction)
up = np.array([1, 0, 0])
right = np.array([0, 1, 0])
far = np.array([0, 0, 1])
# polarization directions of photon pairs
pol_V = np.array([1, 0])
pol_H = np.array([0, 1])
pol_deg = lambda angle: np.cos(np.deg2rad(angle)) * pol_V + np.sin(np.deg2rad(angle)) * pol_H

# constants/parameters (for plotting) ToDo: rework into remaining structure
points = 11
a_d = np.expand_dims(np.linspace(-1, 1, points), 0) * 5e-3  # m detector aperture square size (side length)
cidx = int(np.floor(points/2))
cidxlin = int(np.floor(points**2/2))
revo = 0.5  # One revolution of KM100(CP) kinematic adjusters equals 0.5° angular adjustment

# helper functions:
# Snell's law: calculate internal angles for given external angle
psi = lambda angle_in, n: np.arcsin(np.sin(angle_in) / n)
# group index: n - (dn/dlambda * 1/lambda)
d_wl = 0.01e-9  # delta wavelength for estimation of (Sellmeier) equation derivative
group_index = lambda n, wl: n(wl) - (n(wl + d_wl) - n(wl - d_wl)) / 2 / d_wl * wl
group_vel_disp = lambda n, wl: wl**3 / (2*np.pi * c**2) * (n(wl + d_wl) - 2*n(wl) + n(wl - d_wl))/d_wl**2


class Crystal:
    cname = ''
    material = 'undefined'
    thickness = 0.0  # thickness of the crystal in m
    v_oa = np.array([0, 0, 1])  # initialize optical axis vector along k-vector of pump beam
    v_snc = np.array([0, 0, 1])  # surface normal of crystal
    # rotations are applied to v_oa and/or v_snc in roughly this order:
    cutangle_ud = 0.0  # cutangle (rad) along up/down direction
    cutangle_lr = 0.0  # cutangle (rad) along left/right direction
    rotation = 0.0  # rotation (rad) around "far" direction (pump beam) - usually a rotation of the optics in its mount
    tiltangle_ud = 0.0  # tiltangle (rad) along up/down direction
    tiltangle_lr = 0.0  # tiltangle (rad) along left/right direction
    plotted_debug = False

    def __init__(self, cname: str, material: str, thickness: float, cutangle_ud: float = 0.0,
                 cutangle_lr: float = 0.0, rotation: float = 0.0, tiltangle_ud: float = 0.0,
                 tiltangle_lr: float = 0.0, rotate_tilt: bool = False):
        """
        Initialize class Crystal with the following properties. The orientation unit vectors of optical axis (v_oa)
        and surface normal (v_snc) are calculated automatically.

        CrystalSystem class may add additional attributes to store specific walk-offs in this crystal.

        :param cname:           Descriptive name for crystal
        :param material:        Material to use for calculation of refractive indices.
                                One out of ['BBO', 'alpha-BBO', 'beta-BBO', 'YVO', 'YVO-T', 'YVO-L', 'Quartz']
        :param thickness:       Thickness of this crystal, given in meters.
        :param cutangle_ud:     Crystal cut-angle (deg) along up/down direction (converted to rad internally)
        :param cutangle_lr:     Crystal cut-angle (deg) along left/right direction (converted to rad internally)
        :param rotation:        Rotation (deg) of crystal around it's surface normal vector (converted to rad internally)
        :param tiltangle_ud:    Tilt (deg) of the surface normal along up/down direction  (converted to rad internally)
        :param tiltangle_lr:    Tilt (deg) of the surface normal along left/right direction  (converted to rad internally)
        :param rotate_tilt:     Also apply rotation to tilt, i.e. rotate v_snc around 'far' direction
        """
        self.cname = cname
        if material not in ['BBO', 'beta-BBO-T', 'BBO-T', 'beta-BBO',
                            'alpha-BBO', 'a-BBO', 'alpha-BBO-N', 'a-BBO-N',
                            'YVO', 'YVO-T', 'YVO-L', 'Quartz']:
            raise ValueError(f'Material {material:s} undefined for crystal {cname:s}')
        self.material = material
        self.thickness = thickness
        self.cutangle_ud = np.deg2rad(cutangle_ud)  # cutangle (rad) along up/down direction
        self.cutangle_lr = np.deg2rad(cutangle_lr)  # cutangle (rad) along left/right direction
        self.tiltangle_ud = np.deg2rad(tiltangle_ud)  # tiltangle (rad) along up/down direction
        self.tiltangle_lr = np.deg2rad(tiltangle_lr)  # tiltangle (rad) along left/right direction
        self.rotation = np.deg2rad(rotation)  # rotation (rad) around surface normal axis

        v_oa = ro.from_rotvec(right * self.cutangle_ud).apply(self.v_oa)
        v_oa = ro.from_rotvec(up * self.cutangle_lr).apply(v_oa)
        if not rotate_tilt:
            v_oa = ro.from_rotvec(self.v_snc * self.rotation).apply(v_oa)
        v_oa = ro.from_rotvec(right * self.tiltangle_ud).apply(v_oa)
        self.v_oa = ro.from_rotvec(up * self.tiltangle_lr).apply(v_oa)
        if rotate_tilt:
            self.v_oa = ro.from_rotvec(self.v_snc * self.rotation).apply(self.v_oa)

        self.v_snc = ro.from_rotvec(right * self.tiltangle_ud).apply(self.v_snc)
        self.v_snc = ro.from_rotvec(up * self.tiltangle_lr).apply(self.v_snc)
        if rotate_tilt:
            # note that 'far' equals self.v_snc before application of tilt -> v_snc is rotated the same way as v_oa
            self.v_snc = ro.from_rotvec(far * self.rotation).apply(self.v_snc)
    
    def copy(self, cname: str = None, delta_rotation: float = 0, mirror_tilt_lr: bool = False,
             mirror_tilt_ud: bool = False, rotate_tilt: bool = False):
        """
        Returns an independent copy of this crystal. Optionally with new name, offset rotation or opposite sign of
        left/right tilt.
        :param cname:               New name of crystal copy, if not None (default)
        :param delta_rotation:      Offset to current rotation (deg) of crystal around surface normal axis.
        :param mirror_tilt_lr:      Change sign of tilt angle left/right, if true (default: false).
        :param mirror_tilt_ud:      Change sign of tilt angle up/down, if true (default: false).
        :param rotate_tilt:         Whether to rotate the tilt axes as well.
        :return:                    New Crystal instance.
        """
        if cname is None:
            cname = self.cname
        # note that we have to convert between internally stored angles in radians and input angles in degrees.
        return Crystal(cname, self.material, self.thickness, np.rad2deg(self.cutangle_ud), np.rad2deg(self.cutangle_lr),
                       np.rad2deg(self.rotation)+delta_rotation,
                       -np.rad2deg(self.tiltangle_ud) if mirror_tilt_ud else np.rad2deg(self.tiltangle_ud),
                       -np.rad2deg(self.tiltangle_lr) if mirror_tilt_lr else np.rad2deg(self.tiltangle_lr),
                       rotate_tilt)

    def __str__(self):
        """String representation for printing."""
        return f'{self.cname}'

    def __repr__(self):
        """String representation for debugger."""
        return f'{self.cname}: OA: {self.v_oa}, SurfNormal: {self.v_oa}, ID: {id(self)}'

    def cutangle_eff(self, deg: bool = False) -> float:
        """
        Returns angle between surface normal and optical axis (optionally in degrees).
        :param deg:         If true, return value in degrees, otherwise in radians (default: False).
        :return:            Angle between surface normal and optical axis.
        """
        angle = vecangle(self.v_snc, self.v_oa)
        return np.rad2deg(angle) if deg else angle

    def rotation_eff(self, deg: bool = False) -> float:
        """
        Returns effective rotation angle of crystal in mount (optionally in degrees). Experimental!
        :param deg:         If true, return value in degrees, otherwise in radians (default: False).
        :return:            Angle rotation angle of crystal in mount.
        """
        proj_oa2surf90 = np.cross(self.v_snc, self.v_oa)
        proj_right2surf90 = np.cross(self.v_snc, right)
        angle = vecangle(proj_oa2surf90, proj_right2surf90)
        return np.rad2deg(angle) if deg else angle

    def get_ref_indices(self, wavelength: float) \
            -> tuple[float, float, callable, float, float, callable, float, float, callable]:
        """
        Returns refractive & group indices and group velocity dispersion at the given wavelength for this crystal's
        material.
        :param wavelength:      Wavelength (in m)
        :return:                n_o, n_e, n_eff(theta), g_o, g_e, g_eff(theta), gvd_o, gvd_e, gvd_eff(theta)
        """
        # start by defining (Sellmeier) equations for material, depending on wavelength
        if self.material in ['beta-BBO', 'BBO']:
            # source: https://www.newlightphotonics.com/Nonlinear-Optical-Crystals/BBO-Crystals
            # same parameters as SPDCalc.org
            n_o_wl = lambda wl: np.sqrt(2.7359 + 0.01878 / (
                        wl ** 2 * 1e12 - 0.01822) - 0.01354 * wl ** 2 * 1e12)  # note that Sellmeier eq. uses
            n_e_wl = lambda wl: np.sqrt(2.3753 + 0.01224 / (
                        wl ** 2 * 1e12 - 0.01667) - 0.01516 * wl ** 2 * 1e12)  # wavelength in µm (wl defined in m)
        elif self.material in ['beta-BBO-T', 'BBO-T']:
            # same material, but different parameter source (differences acceptably small)
            # source: https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=16384
            n_o_wl = lambda wl: np.sqrt(1 + 0.90291 * wl ** 2 * 1e12 / (wl ** 2 * 1e12 - 0.003926)
                                          + 0.83155 * wl ** 2 * 1e12 / (wl ** 2 * 1e12 - 0.018786)
                                          + 0.76536 * wl ** 2 * 1e12 / (wl ** 2 * 1e12 - 60.01))
            n_e_wl = lambda wl: np.sqrt(1 + 1.151075 * wl ** 2 * 1e12 / (wl ** 2 * 1e12 - 0.007142)
                                          + 0.21803  * wl ** 2 * 1e12 / (wl ** 2 * 1e12 - 0.02259)
                                          + 0.656    * wl ** 2 * 1e12 / (wl ** 2 * 1e12 - 263))
        elif self.material in ['alpha-BBO', 'a-BBO']:
            # only changes to beta-BBO in constant offset parameter 1
            # source https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=6973&tabname=a-BBO (with citation)
            # alternative source: https://www.agoptics.com/Alpha-BBO.html
            # alternative source: https://www.castech.com/product/%CE%B1-BBO---Alpha-Barium-Borate-90.html
            # NOTE: differs from this source: https://www.newlightphotonics.com/Birefringent-Crystals/alpha-BBO-Crystals
            n_o_wl = lambda wl: np.sqrt(2.7471 + 0.01878 / (
                        wl ** 2 * 1e12 - 0.01822) - 0.01354 * wl ** 2 * 1e12)  # note that Sellmeier eq. uses
            n_e_wl = lambda wl: np.sqrt(2.3174 + 0.01224 / (
                        wl ** 2 * 1e12 - 0.01667) - 0.01516 * wl ** 2 * 1e12)  # wavelength in µm (wl defined in m)
        elif self.material in ['alpha-BBO-N', 'a-BBO-N']:
            # same material, but different parameter source (large difference!! for spatial compensation ~16% thickness)
            # source: https://www.newlightphotonics.com/Birefringent-Crystals/alpha-BBO-Crystals
            n_o_wl = lambda wl: np.sqrt(2.67579 + 0.02099 / (
                        wl ** 2 * 1e12 - 0.00470) - 0.00528 * wl ** 2 * 1e12)  # note that Sellmeier eq. uses
            n_e_wl = lambda wl: np.sqrt(2.31197 + 0.01184 / (
                        wl ** 2 * 1e12 - 0.01607) - 0.00400 * wl ** 2 * 1e12)  # wavelength in µm (wl defined in m)
        elif self.material in ['YVO-T', 'YVO']:
            # Yttrium Ortho-Vanadate YVO_4
            # source https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=6973&tabname=YVO4)
            n_o_wl = lambda wl: np.sqrt(3.77879 + 0.07479 / (
                        wl ** 2 * 1e12 - 0.045731) - 0.009701 * wl ** 2 * 1e12)  # note that Sellmeier eq. uses
            n_e_wl = lambda wl: np.sqrt(4.6072 + 0.108087 / (
                        wl ** 2 * 1e12 - 0.052495) - 0.014305 * wl ** 2 * 1e12)  # wavelength in µm (wl defined in m)
        elif self.material == 'YVO-L':
            # Yttrium Ortho-Vanadate YVO_4 (same material, but different parameter source; differences acceptably small)
            # source https://www.lasercomponents.com/de/?embedded=1&file=fileadmin/user_upload/home/Datasheets/diverse-laser-optics/laser-rods-crystals/yvo4crys.pdf&no_cache=1
            # source https://www.newlightphotonics.com/Birefringent-Crystals/Pure-YVO4-Crystals
            n_o_wl = lambda wl: np.sqrt(3.77834 + 0.069736 / (
                        wl ** 2 * 1e12 - 0.04724) - 0.0108133 * wl ** 2 * 1e12)  # note that Sellmeier eq. uses
            n_e_wl = lambda wl: np.sqrt(4.59905 + 0.110534 / (
                        wl ** 2 * 1e12 - 0.04813) - 0.0122676 * wl ** 2 * 1e12)  # wavelength in µm (wl defined in m)
        elif self.material == 'Quartz':
            # note that equations use wavelength in µm (wl defined in m)
            # source: https://www.newlightphotonics.com/v1/quartz-properties.html
            n_o_wl = lambda wl: np.sqrt(2.3573 - 0.01170 * (wl * 1e6) ** 2 + 0.01054 / (wl * 1e6) ** 2 + 1.3414e-4 / (
                        wl * 1e6) ** 4 - 4.4537e-7 / (wl * 1e6) ** 6 + 5.9236e-8 / (wl * 1e6) ** 8)
            n_e_wl = lambda wl: np.sqrt(2.3849 - 0.01259 * (wl * 1e6) ** 2 + 0.01079 / (wl * 1e6) ** 2 + 1.6518e-4 / (
                        wl * 1e6) ** 4 - 1.9474e-6 / (wl * 1e6) ** 6 + 9.3648e-8 / (wl * 1e6) ** 8)
        else:
            raise ValueError(f'Sellmeier-Equations for {self.material:s} undefined.')

        # define theta-dependent (polarization-vector dependent) refractive/group index functions:
        # also dependent on wavelength (required for derivation step during group index calculation)
        n_eff_wl = lambda theta, wl: np.sqrt((n_o_wl(wl) * n_e_wl(wl)) ** 2 /
                                             ((n_e_wl(wl) * np.cos(theta)) ** 2 + (n_o_wl(wl) * np.sin(theta)) ** 2))
        # calculate (extra-)ordinary refractive and group indices at given wavelength
        n_o = n_o_wl(wavelength)
        n_e = n_e_wl(wavelength)
        g_o = group_index(n_o_wl, wavelength)
        g_e = group_index(n_e_wl, wavelength)
        gvd_o = group_vel_disp(n_o_wl, wavelength)
        gvd_e = group_vel_disp(n_e_wl, wavelength)
        # theta-dependent:
        n_eff = lambda theta: n_eff_wl(theta, wavelength)
        g_eff = lambda theta: group_index(lambda wl: n_eff_wl(theta, wl), wavelength)
        gvd_eff = lambda theta: group_vel_disp(lambda wl: n_eff_wl(theta, wl), wavelength)

        return n_o, n_e, n_eff, g_o, g_e, g_eff, gvd_o, gvd_e, gvd_eff

    def calc_walkoffs(self, k_beam: np.array, wavelength: float, pol_vec: np.array = None,
                      redefine_pol_vec: bool = False) -> dict[np.array]:
        """
        Calculate the walk-off effects (phases (rad), travel times (fs), beam displacement (m)) for the given beam.
        :param k_beam:          Collection of ray unit vectors as 2D numpy array. First dimension iterates over rays.
                                Second array dimension contains the ray unit vectors of length 3.
        :param wavelength:      Wavelength (m) of the beam.
        :param pol_vec:         Polarization vectors for each ray (same numpy array format as k_beam).
        :param redefine_pol_vec:Redefine the pol_vec in-place(!) from P = k x v_oa (see [4]). Should only be used in
                                cases where this crystal creates a photon pair.
        :return:                Dictionary with keys ['phi_eff', 'phi_delta_eff', 'travel_time_eff', 'displacement'].
        """
        if 'no_pair-pol_refinement' in legacy_mode:
            redefine_pol_vec = False  # Ignore requested polarization refinement, if this legacy mode is active.
        n_o, n_e, n_eff, g_o, g_e, g_eff, gvd_o, gvd_e, gvd_eff = self.get_ref_indices(wavelength)
        v_ip = np.cross(k_beam, self.v_snc)  # 'plane of incidence' normal vector (used as "rotation vector")
        v_ip_norm = np.linalg.norm(v_ip, axis=1, keepdims=True)  # vector length
        # norm vector length where possible.
        # Otherwise, k_beam = v_snc and v_ip is undefined - use fixed direction instead.
        v_ip = np.where(v_ip_norm != 0, v_ip / v_ip_norm, np.array([0, 1, 0])[np.newaxis, :])

        # helper function to rotate external k_beam to internal k_in in plane of incidence. This is the application of
        # Snell's law to the k vectors.
        k_in = lambda k_out, alpha, psi: ro.from_rotvec(v_ip * (alpha - psi)).apply(k_out)

        alpha = vecangle(k_beam, self.v_snc)  # input/exit angle of photons w.r.t. crystal's surface normal
        
        # calculate ordinary beam (for legacy mode and starting parameters):
        psi_o = psi(alpha, n_o)
        k_o = k_in(k_beam, alpha, psi_o)
        s_o = k_o

        # calculate (effective) extraordinary beam:
        # calculate theta self-consistently, as theta is not equal to cut-angle, but depends on psi_e(theta):
        theta_old = np.NaN  # NaN value ensure that we enter the while loop below.
        iterations = 0
        # approximate start angle (actually, this is only close to the final value,
        # when computing the "more extraordinary" beam. Polarizations close to ordinary will have theta ~0):
        theta = vecangle(self.v_oa, k_o)
        while not np.all(np.abs(theta - theta_old) < np.deg2rad(1e-3)) and iterations < 1000:
            iterations += 1
            theta_old = theta
            psi_e = psi(alpha, n_eff(theta))  # calculate internal angle of beam
            k_e = k_in(k_beam, alpha, psi_e)  # calculate new internal extraordinary beam vectors
            if redefine_pol_vec:
                # This option may be requested in case this crystal generates an ordinarily polarized photon pair.
                # With that knowledge, we can calculate the k-dependent polarization in the crystal according to [2].
                # Type-I process -> generated beam is ordinary and must be perpendicular to k-vector and optical axis:
                pol_vec_in = np.cross(k_o, self.v_oa)
                pol_vec_in /= np.linalg.norm(pol_vec_in, axis=1, keepdims=True)  # ensure this is a unit vector
                # no need to calculate effective theta from polarization, it is zero by definition:
                theta = np.zeros_like(theta_old)
                # calculate pol-vec outside of crystal. This seems to be "neglected" in the discussions of Ref. [2], but
                # at least in [2b], the theoretical calculations presented (e.g. Fig. 3) do not match when using a 16°
                # cone angle directly in eq. (3), but match well, when a smaller internal cone angle due to the n ~1.65
                # ordinary refractive index is taken into account.
                # This is the reverse application of the helper function k_in, which can be achieved by exchanging
                # internal and external angles in the function arguments (compare to final else-part of this
                # if-statement):
                pol_vec[:,:] = k_in(pol_vec_in, psi_e, alpha)
                # useage of colon indexing replaces the original pol_vec in-place
            elif pol_vec is None:
                raise NotImplementedError("Currently, polarization vectors are required to determine theta angle "
                                          "and 'detection' of ordinary beam")
                # ToDo: This is not really useful anymore, as it can't be used to calculate the ordinary beam. 
                #  This method is not aware of the beam type per se and requires the polarization state. 
                #  Possible reworks: 
                #  - If no polarization is given, return extended dict with true ordinary beam parameters as well 
                #    in addition to the extraordinary beam and let the calling function choose.
                #  - Also handle pol_vec to be a string ('o'/'ordinary', 'e'/'extraordinary' or 'eff'/'effective')
                #    and decide what to calculate and return.
                theta = vecangle(self.v_oa, k_e)  # angle between k_e and optical axis
            else:
                # Approximate internal polarization vector by rotating the polarization
                # measured outside (along k_beam) in the same way as k_beam is rotated inside the crystal.
                # This neglects further polarization changing effects (e.g. differences in transmission amplitudes for
                # different polarization components -> see Fresnel equations. In case of almost normal incidence and use
                # of anti-reflection coatings, influence onto polarization state should be negligible).
                pol_vec_in = k_in(pol_vec, alpha, psi_e)
                # calculate effective theta from polarization, instead of beam vector
                theta = np.pi/2 - vecangle(self.v_oa, pol_vec_in)
            if 'theta_calc' in legacy_mode and np.all(np.abs(theta) > np.deg2rad(legacy_theta_threshold)):
                # legacy mode for extraordinary beam
                theta = vecangle(self.v_oa, k_e)  # angle between k_e and optical axis
        if iterations == 1000:
            raise RuntimeError('theta calculation did not converge...')

        # calculate Poynting vector walk-off angle (according to Ref. [1]):
        rho = np.sign(n_o - n_e) * (theta - np.arctan((n_o / n_e) ** 2 * np.tan(theta)))
        # determine rotation operation from k_e to s_e (Poynting vector)
        rotvec_k_e = np.cross(self.v_oa, k_e)  # get vector perpendicular on optical axis and k_e
        rotvec_k_e = rotvec_k_e / np.linalg.norm(rotvec_k_e, axis=1, keepdims=True)  # norm vector length
        # calculate Poynting unit vector (s_e) and its angle (beta) with the crystal's surface normal:
        s_e = ro.from_rotvec(rotvec_k_e * -rho).apply(k_e)
        beta = vecangle(self.v_snc, s_e)

        # calculate phases (equations following Ref. [1]):
        # Note about splitting phi_delta (in comparison to Ref. [1]): Here, we calculate all
        # beams as "(slightly) extraordinary" beams. The sign differences between the beams of both polarizations are
        # factored in, when summing over different crystals. In order to properly split the contributions to the
        # "delta" phase, we're referencing against the (common) surface normal of the crystal, instead to the
        # respective other polarization directly (Ref. [1] always references s_e against s_o).
        # Further note, that this DOES make a difference in case of the crystal pairs, where [1] effectively
        # references wrongly to the ordinary beam, instead of correctly against the surface normal. In the parameter 
        # range investigated during development of this module, this difference effectively flips the sign of the total 
        # phase map of the SPDC pair, which may be mitigated by adding 180° rotation to the SCCs. Overall, the effect is 
        # not perfectly compensated and a notable difference in the phasemap on the order of few tens of degrees may 
        # remain. This change has been verified by checking the actual orientation of the SCCs' optical axes in an 
        # experiment setup.
        
        phase_factor = self.thickness * 2 * np.pi / wavelength
        # ordinary beam (legacy code - normally not required, as we calculate all rays with their effective indices)
        phi_o = phase_factor / np.cos(psi_o) * n_o  # dot(s_o, k_o) = 1 by definition
        phi_delta_o = phase_factor * (listdot(self.v_snc, k_beam) - listdot(s_o, k_beam) / np.cos(psi_o))

        # extraordinary/effective beam
        phi_eff = phase_factor / np.cos(beta) * n_eff(theta) * np.cos(rho)   # dot(s_e, k_e) is rho by definition
        phi_delta_eff = phase_factor * (listdot(self.v_snc, k_beam) - listdot(s_e, k_beam) / np.cos(beta))

        # calculate "pulse" travel times in fs.
        time_factor = self.thickness / c * 1e15
        if 't_walkoff_ign_angles' in legacy_mode:
            # calculate travel time (just use the crystal thickness, following Ref. [1]):
            travel_time_eff = time_factor * g_eff(theta)  # pulse travel time through crystal for this effective beam
            travel_time_o = time_factor * g_o  # pulse travel time through crystal an ordinary beam
        else:
            # calculate travel time (following the Poynting vector through the crystal):
            travel_time_eff = time_factor * g_eff(theta) * np.cos(rho) / np.cos(beta)  # pulse travel time through crystal for this beam
            if 't_walkoff_ign_delta' not in legacy_mode:
                travel_time_eff += time_factor * (listdot(self.v_snc, k_beam) - listdot(s_e, k_beam) / np.cos(beta))
            travel_time_o = time_factor * g_o / np.cos(psi_o)  # pulse travel time through crystal an ordinary beam
            
        # calculate beam displacement (referenced to beam entry-point projected to exit facette along surface normal):
        # Note: Difference between effective and ordinary beam is derived by subtraction of these displacement vectors 
        # by calling function.
        displacement = self.thickness * s_e / np.cos(beta)

        '''
        # intended for debugging purposes only - remove or adjust as suitable
        if self.cname == 'SPDC-2' and np.abs(wavelength - 810e-9) < 1e-9 and not self.plotted_debug:
            self.plotted_debug = True
            quickplot(alpha, r'$\alpha (°)$')
            quickplot(psi_e, r'$\Psi_e (°)$')
            quickplot(beta, r'$\beta (°)$')
            quickplot(theta, r'$\theta (°)$')
            quickplot(rho, r'$\rho (°)$')
            quickplot(vecangle(s_e, k_beam), r'$S_e \cdot k_{beam} (°)$')
            quickplot(phi_eff, r'$\Phi_e (°)$', norm2center=False)
            quickplot(phi_delta_eff, r'$\Phi_\Delta (°)$', norm2center=False)
            #quickplot(phi_tot, r'$\Phi_\mathrm{total, SPDC} (°)$', norm2center=True)
            plt.show()
        '''
        '''
        # intended for debugging only: plot internal beam path
        if self.cname == 'SPDC-2' and np.abs(wavelength - 810e-9) < 1e-9 and not self.plotted_debug:
            fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
            ax.set_xlabel('x up/down')
            ax.set_ylabel('y left/right')
            ax.set_zlabel('z close/far')
            ax.quiver(*-self.v_snc/5, *self.v_snc, length=1.2, arrow_length_ratio=0, color='black')
            ax.quiver(*-self.v_oa/4, *self.v_oa, length=1/2, arrow_length_ratio=0, color='green')
            ax.quiver(0,0,0, *k_e[cidxlin,:], length=1/np.cos(psi_e[cidxlin]), arrow_length_ratio=0, color='red')
            ax.quiver(0,0,0, *k_o[cidxlin,:], length=1/np.cos(psi_o[cidxlin]), arrow_length_ratio=0, color='blue')
            ax.quiver(0,0,0, *s_e[cidxlin,:], length=1/np.cos(beta[cidxlin]), arrow_length_ratio=0)
            ax.quiver(*-k_beam[cidxlin,:]/5, *k_beam[cidxlin,:], length=1/5, arrow_length_ratio=0, color='grey')
            # axis limits must be equal, if angles are to be displayed without distortion:
            ax.set_xlim([-0.1, 0.1])
            ax.set_ylim([-0.1, 0.1])
            ax.set_zlim([-0.2, 1.0])
            plt.show()
        '''

        if 'phi_delta_ref_to_o' in legacy_mode:
            # force referencing phi_delta phase to ordinary beam. As discussed above, this is actually wrong in case of 
            # the SPDC pair, but it will yield equal results for compensation crystals.
            phi_delta_eff -= phi_delta_o
            phi_delta_o = np.zeros_like(phi_delta_o)

        if 'theta_calc' in legacy_mode:
            # determine beam type ((extra-)ordinary) from theta angle and user-defined threshold
            # and print some information to make the user aware of what happened.
            off = 0
            if np.all(np.abs(theta) < np.deg2rad(legacy_theta_threshold)):
                print(f'{self.cname} (wl {wavelength*1e9} nm): returned a true ordinary beam in legacy mode '
                      f'(from pol_vec {pol_vec[cidxlin-off,:]}: theta = %.2f)'
                      % np.rad2deg(np.pi/2 - vecangle(self.v_oa, pol_vec_in)[cidxlin-off]))
                return {'phi_eff': phi_o, 'phi_delta_eff': phi_delta_o, 
                        'travel_time_eff': travel_time_o, 'displacement': displacement}
            else:
                print(f'{self.cname} (wl {wavelength*1e9} nm): returned an extraordinary beam in legacy mode '
                      f'with theta = %.2f° (from pol_vec {pol_vec[cidxlin-off]}: theta = %.2f)'
                      % (np.rad2deg(theta[cidxlin-off]), np.rad2deg(np.pi/2 - vecangle(self.v_oa, pol_vec_in)[cidxlin-off])))
        
        # note additional return statement in if statement above when adding code here!
        return {'phi_eff': phi_eff, 'phi_delta_eff': phi_delta_eff, 
                'travel_time_eff': travel_time_eff, 'displacement': displacement}


class CrystalSystem:
    def __init__(self, csname: str, wavelengths: dict, detectors: dict, tccs: list[Crystal], spdcs: list[Crystal],
                 signal_sccs: list[Crystal], idler_sccs: list[Crystal] = None,
                 beam_polarizations: dict[np.array] = None, spdc_type = 1):
        """
        Initialize CrystalSystem. Requires information about involved beams' wavelengths, detector positioning and the 
        lists of crystals in the beam paths.

        :param csname:              Name of the crystal system (for identification).
        :param wavelengths:         Dictionary with keys ['pump', 'signal', 'idler'] to specify the beam wavelengths in 
                                    meters. Only pump or signal is required, the other parameters are determined 
                                    automatically (assuming a degenerate SPDC process). Warning: Dict may be modified 
                                    in place.
        :param detectors:           Dictionary with keys ['hoa', 'r_aperture', 'distance', 'points']. Specifies where
                                    detectors are placed (assuming mirror-symmetric setup for a degenerate SPDC
                                    process) and the radius of the detector aperture (calculated field of rays will be a
                                    square area around that radius). 'points' specifies the number of data points along
                                    both square dimensions.
        :param tccs:                List of crystals used for temporal (pre-)compensation.
        :param spdcs:               List of crystals in the SPDC crystal pair/stack. Creation of photon pairs for each
                                    polarization is assumed to happen ONLY in the first crystal with better overlap
                                    between optical axis and beam polarization.
        :param signal_sccs:         List of crystals used for spatial compensation (potentially also temporal post-
                                    compensation), which affect the photons in the signal beam path.
        :param idler_sccs:          Similar to signal_sccs, but for idler beam path. Must have same list length. May use
                                    identical crystals, but requires unique copies of the Crystal (because walk-off
                                    information is stored inside as well). If None, automatically uses a copy of the
                                    signal_sccs (default).
        :param beam_polarizations:  Dictionary with keys ['pump', 'signal', 'idler'] to overwrite default polarization
                                    vectors (type-I SPDC process: V/H pump polarizations produce HH/VV polarized pairs).
                                    The default does not include the Migdall effect (see Ref. [2]). Input vectors are
                                    1D numpy arrays of length 2 (specifying the polarization measured along the
                                    beam's central ray). They are used to calculate 2D numpy arrays of length (rays, 3)
                                    stored internally (specifying the three-dimensional polarization vector rotated for
                                    each ray of the beam (outside the crystals)).
        :param spdc_type:           Type of the SPDC process (default: 1). Currently supported: crossed Type-I (1) and
                                    Type-II (2).
        """
        self.csname = csname
        # Some checks on the input wavelengths
        if not any(key in wavelengths for key in ['pump', 'signal', 'idler']):
            raise ValueError('No proper wavelength information given.')
        elif 'pump' in wavelengths and ('signal' not in wavelengths or 'idler' not in wavelengths):
            wavelengths['signal'] = wavelengths['pump'] * 2
            wavelengths['idler'] = wavelengths['pump'] * 2
        elif 'signal' in wavelengths and 'pump' not in wavelengths:
            wavelengths['pump'] = wavelengths['signal'] / 2

        if np.abs(wavelengths['signal'] - wavelengths['idler']) > 1e-11:
            raise NotImplementedError('Signal and Idler wavelength differ. Non-degenerate SPDC processes not supported.')
        # no further wavelength checks otherwise
        self.wavelengths = wavelengths

        self.detectors = detectors.copy()  # make a (shallow) copy of the dict, as we're adding a value for internal use
        self.detectors['hoa_rad'] = np.deg2rad(self.detectors['hoa'])  # add half-opening angle converted to rad

        # store crystal lists (no copies unless stated otherwise!):
        # automatically convert single Crystal type input into a list of length 1.
        # No checks against other wrong input types
        self.tccs = [tccs] if isinstance(tccs, Crystal) else tccs
        self.spdcs = [spdcs] if isinstance(spdcs, Crystal) else spdcs
        self.signal_sccs = [signal_sccs] if isinstance(signal_sccs, Crystal) else signal_sccs
        if idler_sccs is None:
            # in this case we use a (deep) copy of the crystal list
            # (i.e. copies of the Crystal instances, not the list object)
            self.idler_sccs = [scc.copy() for scc in self.signal_sccs]
        else:
            self.idler_sccs = [idler_sccs] if isinstance(idler_sccs, Crystal) else idler_sccs
        if len(self.idler_sccs) != len(self.signal_sccs):
            raise NotImplementedError("Can't handle different numbers compensation crystals in signal and idler beam.")

        # some list input validation
        all_crystals = self.tccs + self.spdcs + self.signal_sccs + self.idler_sccs
        if not all((isinstance(crys, Crystal) for crys in all_crystals)):
            raise TypeError('Crystal input lists must contain objects of type Crystal!')
        self.n_crystals = len(all_crystals)
        unique_crystals = set(all_crystals)  # a set eliminates identical objects/instances from the list.
        if len(unique_crystals) < self.n_crystals:
            warn('Crystal input lists contain the same Crystal instance multiple times. '
                 'It is advisable to use identical copies instead.', RuntimeWarning, 2)
        self.all_crystals = all_crystals

        # more walk-off calculations than crystals, as in SPDC crystals we have to account for both wavelengths:
        self.n_walkoffs = len(self.tccs) + 2*len(self.spdcs) + len(self.signal_sccs)

        # use default (idealized) input beam polarizations, if not given by user
        if beam_polarizations is None:
            self.beam_polarizations = {'pump': [pol_H, pol_V], 'signal': [pol_V, pol_H], 'idler': [pol_V, pol_H]}
        else:
            self.beam_polarizations = deepcopy(beam_polarizations)
        # just a placeholder for polarization fields of rays (calculated later):
        self.polarizations = {'pump': [None,None], 'signal': [None,None], 'idler': [None,None]}

        self.spdc_type = spdc_type
        if spdc_type == 2 and 'no_pair-pol_refinement' not in legacy_mode:
            warn("Type-II SPDC not compatible with automatic polarization refinement. "
                 "Activate legacy mode 'no_pair-pol_refinement'.", RuntimeWarning, 2)

        # initialize field of rays (with k vectors and polarization vectors):
        self.init_rays()

    def init_rays(self):
        """
        Initialize field of rays (with k vectors and polarization vectors).
        """
        self.k_p = np.array([0, 0, 1])  # k-vector of pump beam

        # calculate detector grid:
        # Detector aperture square grid coordinates (points along each side). Expanded to two dimensions for meshgrid
        # operation below.
        a_d = np.expand_dims(np.linspace(-1, 1, self.detectors['points']), 0) * self.detectors['r_aperture']
        # determine angle grids (referenced from pump beam)
        da_ud_signal = np.arctan(a_d / self.detectors['distance'])  # detection angle up/down
        da_lr_signal = np.arctan(a_d / self.detectors['distance']) + self.detectors['hoa_rad']  # detection angle left/right
        # The following ensures that we can just add the phasemaps (assuming symmetric signal/idler beams), 
        # as photon pairs arrive at same opening angle with opposite sign. 
        da_lr_idler = - da_lr_signal
        # If a photon arrives a bit above the pump beam plane at one detector, the other one arrives below:
        da_ud_idler = - da_ud_signal
        # calculate meshgrid and flatten to 1D arrays (many of the numpy vector operations can handle a list of vectors,
        # but not grids):
        da_ud_signal, da_lr_signal = [a.reshape(-1, 1) for a in np.meshgrid(da_ud_signal, da_lr_signal)]
        da_ud_idler, da_lr_idler = [a.reshape(-1, 1) for a in np.meshgrid(da_ud_idler, da_lr_idler)]
        
        # calculate photon pair beam directions by rotation from pump direction to detector grid angles:
        # Combine both rotations into one matrix (is reused later). Rotations are applied from right to left, so order
        # of the product is important and must be consistent for signal/idler and k-/pol-vectors.
        rot_signal = ro.from_rotvec(up[np.newaxis] * da_lr_signal) * ro.from_rotvec(right[np.newaxis] * da_ud_signal)
        self.k_signal = rot_signal.apply(self.k_p)
        # with a symmetric setup k_idler should just be equal to k_signal with opposite signs in the first 
        # two vector dimensions. Nevertheless, it is derived separately from the detector setup above.
        rot_idler = ro.from_rotvec(up[np.newaxis] * da_lr_idler) * ro.from_rotvec(right[np.newaxis] * da_ud_idler)
        self.k_idler = rot_idler.apply(self.k_p)

        # calculate three-dimensional polarization vectors for ray field from input beam polarization (measured along
        # k_beam). Changes for k_p also required, if k_p not along 0,0,1:
        for p, pol_vec in enumerate(self.beam_polarizations['signal']):
            pol_vec = np.append(pol_vec, 0)
            # rotate to be perpendicular to actual k_beam (this is the same transformation, that generates k_beam from k_p)
            self.polarizations['signal'][p] = rot_signal.apply(pol_vec[np.newaxis,:])
            # consistency check: is pol perpendicular to beam direction?
            if np.any(np.abs(np.abs(vecangle(self.polarizations['signal'][p], self.k_signal)) - np.pi/2) > np.deg2rad(1e-3)):
                raise ValueError('Signal polarization not perpendicular to beam direction.')
        for p, pol_vec in enumerate(self.beam_polarizations['idler']):
            pol_vec = np.append(pol_vec, 0)
            # rotate to be perpendicular to actual k_beam (this is the same transformation, that generates k_beam from k_p)
            self.polarizations['idler'][p] = rot_idler.apply(pol_vec[np.newaxis,:])
            # consistency check: is pol perpendicular to beam direction?
            if np.any(np.abs(np.abs(vecangle(self.polarizations['idler'][p], self.k_idler)) - np.pi/2) > np.deg2rad(1e-6)):
                raise ValueError('Idler polarization not perpendicular to beam direction.')
        for p, pol_vec in enumerate(self.beam_polarizations['pump']):
            pol_vec = np.append(pol_vec, 0)
            pol_vec = np.broadcast_to(pol_vec[np.newaxis,:], shape= self.polarizations['signal'][0].shape)
            self.polarizations['pump'][p] = pol_vec  # ToDo: check whether rotation is required in some unusual cases
        # also store reference polarization vectors for calculation of polarization angles
        # (following a similar logic to Ref [2]):
        self.ref_pol_vecs = {'signal': rot_signal.apply(np.append(pol_V,0)[np.newaxis,:]),
                             'idler':  rot_idler.apply(np.append(pol_V,0)[np.newaxis,:])}

        # broadcast (copy rays) to detector array dimensions (= same dimensions as k_signal & k_idler):
        self.k_p = np.broadcast_to(self.k_p[np.newaxis,:], (self.detectors['points'] ** 2, 3))

    def copy(self, csname: str = None, rotate90: bool = True):
        """
        Returns an independent copy of this CrystalSystem.

        :param csname:      Optional: New name for copied crystal system (default: None -> Copy old name).
        :param rotate90:    Optionally rotate the TCC and SPDC crystals by 90° and the SCCs by 180° (usually yields a
                            similarly compensated system, but temporal walk-off differs by twice the contribution of
                            SCCs).
        :return:            New CrystalSystem instance.
        """
        # Note: If there surface normales of TCCs and SPDC crystals are tilted, this tilt should be rotated as well, if
        # the system is rotated:
        new_tccs = [old.copy(delta_rotation=90*rotate90,rotate_tilt=rotate90) for old in self.tccs]
        new_spdcs = [old.copy(delta_rotation=90*rotate90,rotate_tilt=rotate90) for old in self.spdcs]
        # Note: If the system is rotated by 90°, the SCCs must be rotated by 180°, but tilt remains unchanged:
        new_signal_sccs = [old.copy(delta_rotation=180*rotate90) for old in self.signal_sccs]
        new_idler_sccs = [old.copy(delta_rotation=180*rotate90) for old in self.idler_sccs]
        new_name = self.csname if csname is None else csname

        return CrystalSystem(new_name, self.wavelengths, self.detectors, new_tccs, new_spdcs,
                             new_signal_sccs, new_idler_sccs, self.beam_polarizations)

    def __str__(self):
        """String representation for printing."""
        return f'{self.csname}'

    def __repr__(self):
        """String representation for debugger."""
        return f'{self.csname}: Crystals: [{",".join(map(str,self.all_crystals))}], ID: {id(self)}'

    def sum_temp_walkoffs(self) -> None:
        """
        Triggers the necessary walk-off calculations for each polarization, beam and crystal and calculates the
        differences between both photon pair polarizations. Results are stored as attributes of the Crystals and the
        CrystalSystem, as applicable.
        """
        # set up container for both polarizations, signal/idler beams and each relevant beam per crystal
        travel_times = np.zeros([2, 2, self.n_walkoffs], dtype=object)  # require object type (elements will be arrays)
        w_idx = -1  # index (will be incremented from zero to self.n_walkoffs-1)
        for tcc in self.tccs:
            w_idx += 1
            # in a type-I SPDC process, pump polarizations are reversed with respect to photon pairs. So we have to
            # apply the proper polarization to the walk-off calculation. The index p always refers to the first/second
            # polarization of a photon-pair generation process.
            for p, pol in enumerate(self.polarizations['pump']):
                walkoffs = tcc.calc_walkoffs(self.k_p, self.wavelengths['pump'], pol)
                travel_times[p, 0, w_idx] = walkoffs['travel_time_eff']
                travel_times[p, 1, w_idx] = travel_times[p, 0, w_idx]  # same effect for signal/idler
            tcc.t_walkoff = travel_times[0, 0, w_idx] - travel_times[1, 0, w_idx]

        # keep track of which polarization has already been generated (no pair before, no pump after):
        present_pol = [False, False]
        for spdc in self.spdcs:
            # heuristically determine which pair polarization is produced by this crystal:
            # pairs are generated in the crystal have a larger overlap between optical axis and their pump polarization.
            overlaps = np.array([np.max(np.abs(listdot(pol, spdc.v_oa))) for pol in self.polarizations['pump']])
            # index of the generated polarization (follows the same logic as index p):
            create_pol = np.argmax(overlaps)

            # again, pick the correct polarizations for the pump beam:
            w_idx += 1
            for p, pol in enumerate(self.polarizations['pump']):
                if self.spdc_type == 2:
                    # for type-II SPDC generate both polarizations in one crystal
                    create_pol = p
                if present_pol[p]:
                    # this pair already exists, no pump contribution anymore
                    travel_times[p, 0, w_idx] = 0
                    travel_times[p, 1, w_idx] = 0
                else:
                    walkoffs = spdc.calc_walkoffs(self.k_p, self.wavelengths['pump'], pol)
                    travel_times[p, 0, w_idx] = walkoffs['travel_time_eff']
                    travel_times[p, 1, w_idx] = travel_times[p, 0, w_idx]  # same effect for signal/idler
                    # generating polarization only travels half the distance; this contribution is assumed to cancel out
                    # in legacy mode:
                    # (note, this is correct, as p is a counting index, not the polarization of the pump):
                    if p == create_pol:
                        travel_times[p, :, w_idx] = 0 if 'eq_pair_t_walkoff' in legacy_mode \
                            else travel_times[p, :, w_idx] / 2
                        present_pol[p] = True  # remember, that this pair-pol has been created.
            # store temporal walk-off contributions in this crystal (partial, addition below!):
            spdc.t_walkoff_signal = travel_times[0, 0, w_idx] - travel_times[1, 0, w_idx]
            spdc.t_walkoff_idler = travel_times[0, 1, w_idx] - travel_times[1, 1, w_idx]

            # continue with proper photon pair polarizations and use different beams for signal and idler:
            w_idx += 1
            for p, _ in enumerate(self.polarizations['signal']):
                if self.spdc_type == 2:
                    # for type-II SPDC generate both polarizations in one crystal
                    create_pol = p
                if not present_pol[p]:
                    # this pair does not exist yet, no contribution
                    travel_times[p, 0, w_idx] = 0
                    travel_times[p, 1, w_idx] = 0
                else:
                    walkoffs = spdc.calc_walkoffs(self.k_signal, self.wavelengths['signal'],
                                                  self.polarizations['signal'][p], redefine_pol_vec= p == create_pol)
                    travel_times[p, 0, w_idx] = walkoffs['travel_time_eff']
                    walkoffs = spdc.calc_walkoffs(self.k_idler, self.wavelengths['idler'],
                                                  self.polarizations['idler'][p], redefine_pol_vec= p == create_pol)
                    travel_times[p, 1, w_idx] = walkoffs['travel_time_eff']
                    # generated polarization only travels half the distance; this contribution is assumed to cancel out
                    # in legacy mode:
                    if p == create_pol:
                        travel_times[p, :, w_idx] = 0 if 'eq_pair_t_walkoff' in legacy_mode \
                            else travel_times[p, :, w_idx] / 2
            # add to stored temporal walk-off contributions in this crystal (see above):
            spdc.t_walkoff_signal += travel_times[0, 0, w_idx] - travel_times[1, 0, w_idx]
            spdc.t_walkoff_idler += travel_times[0, 1, w_idx] - travel_times[1, 1, w_idx]

        # treat signal and idler beams and their SCCs in the same loop. This requires the list to be of equal
        # length. ToDo: Check whether it makes sense to rewrite this into two loops to allow different number of
        # crystals.
        for s_scc, i_scc in zip(self.signal_sccs, self.idler_sccs):
            w_idx += 1
            for p, _ in enumerate(self.polarizations['signal']):
                # get walkoffs for signal and idler separately:
                # keep in mind that for Type-II SPDC we assume a perfect HWP to flip H&V polarizations before the SCCs,
                # hence the addition-modulo operation on the polarization index: (p+self.spdc_type==2)%2
                walkoffs = s_scc.calc_walkoffs(self.k_signal, self.wavelengths['signal'],
                                               self.polarizations['signal'][p])
                travel_times[(p+self.spdc_type==2)%2, 0, w_idx] = walkoffs['travel_time_eff']
                walkoffs = i_scc.calc_walkoffs(self.k_idler, self.wavelengths['idler'], self.polarizations['idler'][p])
                travel_times[(p+self.spdc_type==2)%2, 1, w_idx] = walkoffs['travel_time_eff']
            s_scc.t_walkoff = travel_times[0, 0, w_idx] - travel_times[1, 0, w_idx]
            i_scc.t_walkoff = travel_times[0, 1, w_idx] - travel_times[1, 1, w_idx]

        self.travel_times = travel_times  # store for debug or more detailed analysis

        # summation of walk-offs in each crystal type:
        self.temp_walkoff_tccs = sum(tcc.t_walkoff for tcc in self.tccs)
        self.temp_walkoff_s_spdcs = sum(spdc.t_walkoff_signal for spdc in self.spdcs)
        self.temp_walkoff_i_spdcs = sum(spdc.t_walkoff_idler for spdc in self.spdcs)
        self.temp_walkoff_s_sccs = sum(s_scc.t_walkoff for s_scc in self.signal_sccs)
        self.temp_walkoff_i_sccs = sum(i_scc.t_walkoff for i_scc in self.idler_sccs)

        # summation of full system walk-offs for signal, idler and their sum:
        self.temp_walkoff_signal = np.sum(travel_times[0, 0, :]) - np.sum(travel_times[1, 0, :])
        self.temp_walkoff_idler = np.sum(travel_times[0, 1, :]) - np.sum(travel_times[1, 1, :])
        # We care about the total walk-off between H&V polarizations. In case of the crossed Type-I SPDC system, the
        # role of H&V is identical in both arms. However, in Type-II SPDC the roles of H&V are flipped in both arms and
        # we are interessted in the phase difference phi of the state |HV> + e^(i phi) |VH>. If the walk-off between
        # H&V would be identical in both arms, there would not be a difference between the HV and VH state. Thus, we
        # have to calculate the difference in walk-off for the Type-II situation, instead of the sum:
        self.temp_walkoff_total = self.temp_walkoff_signal + self.temp_walkoff_idler * (-1)**(self.spdc_type==2)

    def print_temp_walkoff_summary(self, per_crystal_type: bool = True, per_crystal: bool = False,
                                   per_color: bool = False, advice: bool = True) -> None:
        """
        Prints a summary for total temporal walk-off. More details optional:

        :param per_crystal_type:    Also add summary for each crystal type (default: True).
        :param per_crystal:         Also show walk-off in each crystal (separately for signal and idler, where
                                    applicable) (default: False).
        :param per_color:           Print walk-off separately for pump and pair 'colors'
                                    (default: False, not yet implemented).
        :param advice:              Print advice (recommended thickness or higher/lower cut-angle) for optimal
                                    compensation.
        """
        print('--------------------TEMPORAL WALK-OFF--------------------')
        # ensure that calculation has been run already, by checking presence of results
        if not hasattr(self,'travel_times') or self.travel_times is None:
            self.sum_temp_walkoffs()

        # Determine over-/under-compensation:
        comp_factor = abs(float((self.temp_walkoff_s_spdcs[cidxlin] + self.temp_walkoff_i_spdcs[cidxlin] +
                                 self.temp_walkoff_s_sccs[cidxlin] + self.temp_walkoff_i_sccs[cidxlin]) /
                                (2 * self.temp_walkoff_tccs[cidxlin])))
        comp_type = 'overcompensated' if comp_factor < 1 else 'undercompensated'
        # Note: np.array is not compatible with f-strings (directly), next short notation is using %-format notation
        print(f'Total temporal walkoff in system (signal + idler): %.2f fs ({comp_type:s})'
              % self.temp_walkoff_total[cidxlin])
        if 'pump_bw' in self.wavelengths:
            bandwidth_omega = 2 * np.pi * c * self.wavelengths['pump_bw'] / self.wavelengths['pump']**2
            phase_bandwidth = float(bandwidth_omega * self.temp_walkoff_total[cidxlin] * 1e-15)/2  # rad/s * fs * 1e-15 = rad
            print(f'This equals a phase range of {np.rad2deg(phase_bandwidth):.1f}° '
                  f'(using the pump bandwidth of {self.wavelengths["pump_bw"]*1e9:.2f} nm '
                  f'converted to pair frequencies [divided by 2]).')
        '''if 'bandwidth' in self.detectors:  # incorrect version, as detector bandwidth should scale with GVD
            bandwidth_omega = 2 * np.pi * c * self.detectors['bandwidth'] / self.wavelengths['signal']**2
            phase_bandwidth = float(bandwidth_omega * self.temp_walkoff_total[cidxlin] * 1e-15)  # rad/s * fs * 1e-15 = rad
            print(f'This equals a phase range of {np.rad2deg(phase_bandwidth):.1f}° '
                  f'(using the detector bandwidth of {self.detectors["bandwidth"]*1e9:.0f} nm).')'''
        if advice:
            tcc_total_thick = sum(tcc.thickness for tcc in self.tccs)
            print(f'Recommended temporal compensation crystals total thickness (same cutangle): '
                  f'{np.abs(tcc_total_thick * comp_factor) * 1e3:.3f}mm')
            print(f'Alternatively, {"reduce" if comp_factor < 1 else "increase":s} cutangle at same thickness.')
        if per_crystal_type:
            print('Temporal walkoff in TCCs: %.2f fs' % (2*self.temp_walkoff_tccs[cidxlin]))
            print('Temporal walkoff in SPDCs: %.2f fs' % (self.temp_walkoff_s_spdcs[cidxlin]+self.temp_walkoff_i_spdcs[cidxlin]))
            print('Temporal walkoff in SCCs: %.2f fs' % (self.temp_walkoff_s_sccs[cidxlin]+self.temp_walkoff_i_sccs[cidxlin]))
        if per_crystal:
            for crystal in self.spdcs:
                print('Temporal walkoff (signal) in {crystal.cname} (SPDC): %.2f fs' % crystal.t_walkoff_signal[cidxlin])
                print('Temporal walkoff (idler) in {crystal.cname} (SPDC): %.2f fs' % crystal.t_walkoff_idler[cidxlin])
            for crystal in self.tccs + self.signal_sccs + self.idler_sccs:
                print('Temporal walkoff in {crystal.cname}: %.2f fs' % crystal.t_walkoff[cidxlin])
        if per_color:
            raise NotImplementedError
        print('---------------------------------------------------------')

    def plot_temp_walkoff_summary(self, per_crystal_type: bool = False, sig_idl_separate: bool = False,
                                     show_now: bool = False) -> list[plt.figure]:
        """
        Plots the phasemap of total spatial walk-off at the detector aperture plane. More details optional:

        :param per_crystal_type:    Also show phasemaps for each crystal type (default: True).
        :param sig_idl_separate:    Show requested phasemaps separately for signal and idler, otherwise show their sum
                                    (default: False)
        :param show_now:            Show plots immediately at end of method. Code execution halts until plot windows are
                                    closed (default: False).
        :return:                    List of pyplot Figures.
        """
        # ensure that calculation has been run already, by checking presence of results
        if not hasattr(self, 'travel_times') or self.travel_times is None:
            self.sum_temp_walkoffs()
        figs = []
        if 'pump_bw' in self.wavelengths:
            bandwidth_omega = 2 * np.pi * c * self.wavelengths['pump_bw'] / self.wavelengths['pump'] ** 2
            phase_bandwidth = bandwidth_omega * self.temp_walkoff_total * 1e-15 / 2 # rad/s * fs * 1e-15 = rad
            '''if 'bandwidth' in self.detectors:  # incorrect version, as detector bandwidth should scale with GVD
                bandwidth_omega = 2 * np.pi * c * self.detectors['bandwidth'] / self.wavelengths['signal']**2
                phase_bandwidth = bandwidth_omega * self.temp_walkoff_total * 1e-15  # rad/s * fs * 1e-15 = rad'''
        else:
            raise NotImplementedError('Currently requires a detector bandwidth for suitable plot units...')

        if sig_idl_separate:
            raise NotImplementedError()
        else:
            figs.append(quickplot(phase_bandwidth, r'$d\Phi_\mathrm{total,system} (°)$', norm2center=False))
            if per_crystal_type:
                raise NotImplementedError()
        for fig in figs:
            fig.suptitle(f'{self.csname}')
        if show_now:
            print('Waiting for plot windows to be closed...')
            plt.show()
        return figs

    def sum_spatial_walkoffs(self) -> None:
        """
        Triggers the necessary walk-off calculations for each polarization, beam and crystal and calculates the
        differences between both photon pair polarizations. Results are stored as attributes of the Crystals and the
        CrystalSystem, as applicable. The overall structure is very similar to method 'sum_temp_walkoffs', but it makes
        sense to keep these methods separated for a clearer, streamlined reading experience.
        """
        # set up container for both polarizations, signal/idler beams and each relevant beam per crystal
        spatial_phases = np.zeros([2, 2, self.n_walkoffs], dtype=object)
        w_idx = -1
        for tcc in self.tccs:
            w_idx += 1
            # walkoff in temporal compensation crystals is not angle dependent, so right now, we could ignore it, as
            # it would result in a flat offset for the full phasemap at the detector. But since we also normalize
            # to the central ray at the detector, this offset is lost anyway.
            # However, this offset defines the adjustable phase-offset between VV and HH photon pair states, so this
            # is actually another bit of useful information. And while at it, we also calculate beam displacement for
            # the pump beam (could be moved to separate function). Both properties are stored separately and
            # specifically for TCCs.
            beam_disp = 0  # type will be converted to the proper numpy array automatically.
            for p, _ in enumerate(self.polarizations['pump']):
                walkoffs = tcc.calc_walkoffs(self.k_p, self.wavelengths['pump'],self.polarizations['pump'][p])
                # EXPERIMENTAL! Phase contribution of pump /2 (split equally between signal and idler)
                spatial_phases[p, 0, w_idx] = (walkoffs['phi_eff'] + walkoffs['phi_delta_eff'])/2
                # alternate sign for both polarizations to calculate difference on the fly in a single variable:
                beam_disp -= (-1)**p * walkoffs['displacement']
            spatial_phases[:, 1, w_idx] = spatial_phases[:, 0, w_idx]  # same effect for signal/idler
            tcc.phase_diff = spatial_phases[0, 0, w_idx] - spatial_phases[1, 0, w_idx]
            tcc.beam_disp = beam_disp

        # keep track of which polarization has already been generated (no pair before, no pump after):
        present_pol = [False, False]
        for spdc in self.spdcs:
            # heuristically determine which pair polarization is produced by this crystal:
            # pairs are generated in the crystal have a larger overlap between optical axis and their pump polarization.
            overlaps = np.array([np.max(np.abs(listdot(pol, spdc.v_oa))) for pol in self.polarizations['pump']])
            create_pol = np.argmax(overlaps)

            # again, pick the correct polarizations for the pump beam:
            w_idx += 1
            # again, we could ignore the spatial walk-off for the pump beam, as it is not angle dependent (see above)...
            for p, pol in enumerate(self.polarizations['pump']):
                if self.spdc_type == 2:
                    # for type-II SPDC generate both polarizations in one crystal
                    create_pol = p
                if present_pol[p]:
                    # this pair already exists, no pump contribution anymore
                    spatial_phases[p, 0, w_idx] = 0
                    spatial_phases[p, 1, w_idx] = 0
                else:
                    walkoffs = spdc.calc_walkoffs(self.k_p, self.wavelengths['pump'], pol)
                    # EXPERIMENTAL! Phase contribution of pump /2 (split equally between signal and idler)
                    spatial_phases[p, 0, w_idx] = (walkoffs['phi_eff'] + walkoffs['phi_delta_eff'])/2
                    spatial_phases[p, 1, w_idx] = spatial_phases[p, 0, w_idx]  # same effect for signal/idler
                    # generating polarization only travels half the distance; this contribution is assumed to cancel out
                    # in legacy mode:
                    # (note, this is correct, as p is a counting index, not the polarization of the pump):
                    if p == create_pol:
                        spatial_phases[p, :, w_idx] = 0 if 'eq_pair_s_walkoff' in legacy_mode \
                            else spatial_phases[p, :, w_idx] / 2
                        present_pol[p] = True  # remember, that this pair-pol has been created.
                        #print(f'Created pair in {spdc.cname}.')
            # spatial walkoff in this crystal is the difference between both polarizations (1 of 2: pump-part)
            spdc.s_walkoff_signal = spatial_phases[0, 0, w_idx] - spatial_phases[1, 0, w_idx]
            spdc.s_walkoff_idler = spatial_phases[0, 1, w_idx] - spatial_phases[1, 1, w_idx]

            # continue with proper photon pair polarizations and use different beams for signal and idler:
            w_idx += 1
            for p, _ in enumerate(self.polarizations['signal']):
                if self.spdc_type == 2:
                    # for type-II SPDC generate both polarizations in one crystal
                    create_pol = p
                if not present_pol[p]:
                    # this pair does not exist yet, no contribution
                    spatial_phases[p, 0, w_idx] = 0
                    spatial_phases[p, 1, w_idx] = 0
                else:
                    walkoffs = spdc.calc_walkoffs(self.k_signal, self.wavelengths['signal'],
                                                  self.polarizations['signal'][p], redefine_pol_vec= p == create_pol)
                    spatial_phases[p, 0, w_idx] = walkoffs['phi_eff'] + walkoffs['phi_delta_eff']
                    walkoffs = spdc.calc_walkoffs(self.k_idler, self.wavelengths['idler'],
                                                  self.polarizations['idler'][p], redefine_pol_vec= p == create_pol)
                    spatial_phases[p, 1, w_idx] = walkoffs['phi_eff'] + walkoffs['phi_delta_eff']
                    # generated polarization only travels half the distance; this contribution is assumed to cancel out
                    # in legacy mode:
                    if p == create_pol:
                        spatial_phases[p, :, w_idx] = 0 if 'eq_pair_s_walkoff' in legacy_mode \
                            else spatial_phases[p, :, w_idx] / 2
            # spatial walkoff in this crystal is the difference between both polarizations (2 of 2: pair-part)
            spdc.s_walkoff_signal += spatial_phases[0, 0, w_idx] - spatial_phases[1, 0, w_idx]
            spdc.s_walkoff_idler += spatial_phases[0, 1, w_idx] - spatial_phases[1, 1, w_idx]

        # Treat signal and idler beams and their SCCs in the same loop. This requires the list to be of equal
        # length. ToDo: Check whether it makes sense to rewrite this into two loops to allow different number of
        # crystals.
        for s_scc, i_scc in zip(self.signal_sccs, self.idler_sccs):
            w_idx += 1
            # get walkoffs for signal and idler separately.
            for p, _ in enumerate(self.polarizations['signal']):
                # keep in mind that for Type-II SPDC we assume a perfect HWP to flip H&V polarizations before the SCCs,
                # hence the addition-modulo operation on the polarization index: (p+self.spdc_type==2)%2
                walkoffs = s_scc.calc_walkoffs(self.k_signal, self.wavelengths['signal'], self.polarizations['signal'][p])
                spatial_phases[(p+self.spdc_type==2)%2, 0, w_idx] = walkoffs['phi_eff'] + walkoffs['phi_delta_eff']
                walkoffs = i_scc.calc_walkoffs(self.k_idler, self.wavelengths['idler'], self.polarizations['idler'][p])
                spatial_phases[(p+self.spdc_type==2)%2, 1, w_idx] = walkoffs['phi_eff'] + walkoffs['phi_delta_eff']
            # spatial walk-offs in these crystals are the differences between both polarizations:
            s_scc.s_walkoff = spatial_phases[0, 0, w_idx] - spatial_phases[1, 0, w_idx]
            i_scc.s_walkoff = spatial_phases[0, 1, w_idx] - spatial_phases[1, 1, w_idx]

        self.spatial_phases = spatial_phases  # save for debug or more detailed analysis

        # summation of walk-offs in each crystal type:
        self.spatial_walkoff_s_tccs = sum([tcc.phase_diff for tcc in self.tccs])
        self.spatial_walkoff_s_spdcs = sum([spdc.s_walkoff_signal for spdc in self.spdcs])
        self.spatial_walkoff_i_spdcs = sum([spdc.s_walkoff_idler for spdc in self.spdcs])
        self.spatial_walkoff_s_sccs = sum([s_scc.s_walkoff for s_scc in self.signal_sccs])
        self.spatial_walkoff_i_sccs = sum([i_scc.s_walkoff for i_scc in self.idler_sccs])

        # summation of full system walk-offs for signal, idler and their sum:
        self.spatial_walkoff_signal = np.sum(spatial_phases[0, 0, :]) - np.sum(spatial_phases[1, 0, :])
        self.spatial_walkoff_idler = np.sum(spatial_phases[0, 1, :]) - np.sum(spatial_phases[1, 1, :])
        # We care about the total walk-off between H&V polarizations. In case of the crossed Type-I SPDC system, the
        # role of H&V is identical in both arms. However, in Type-II SPDC the roles of H&V are flipped in both arms and
        # we are interessted in the phase difference phi of the state |HV> + e^(i phi) |VH>. If the walk-off between
        # H&V would be identical in both arms, there would not be a difference between the HV and VH state. Thus, we
        # have to calculate the difference in walk-off for the Type-II situation, instead of the sum:
        self.spatial_walkoff_total = self.spatial_walkoff_signal + self.spatial_walkoff_idler * (-1)**(self.spdc_type==2)

    def print_tcc_phase_and_displacement_summary(self, per_crystal: bool = True) -> None:
        print('----------TCC PHASE OFFSET AND BEAM DISPLACEMENT---------')
        # ensure that calculation has been run already, by checking presence of results
        if not hasattr(self,'spatial_phases') or self.spatial_phases is None:
            self.sum_spatial_walkoffs()

        if per_crystal:
            for tcc in self.tccs:
                print(f'Beam displacement in {tcc.cname:s}: '
                      f'{np.array2string(tcc.beam_disp[cidxlin]*1e6, formatter={"float_kind": lambda x: "%.2f" % x})} µm')
                print(f'Phase offset between polarizations in {tcc.cname:s}: '
                      f'%.2f wavelengths' % (tcc.phase_diff[cidxlin]/(2*np.pi)))
        else:
            raise NotImplementedError('Summation over multiple crystals not yet implemented...')
        print('---------------------------------------------------------')

    def print_spatial_walkoff_summary(self, per_crystal_type: bool = True, per_crystal: bool = False,
                                      sig_idl_separate: bool = False) -> None:
        """
        Prints a summary for total spatial walk-off. More details optional:

        :param per_crystal_type:    Also add summary for each crystal type (default: True).
        :param per_crystal:         Also show walk-off in each crystal (default: False).
        :param sig_idl_separate:    Also show per_crystal_type summary separately for signal and idler,
                                    where applicable (default: False)
        """
        print('---------------------SPATIAL WALK-OFF--------------------')
        # ensure that calculation has been run already, by checking presence of results
        if not hasattr(self,'spatial_phases') or self.spatial_phases is None:
            self.sum_spatial_walkoffs()

        print(f'Total spatial phase range of system (signal + idler): '
              f'{phase_range_deg(self.spatial_walkoff_total):.1f}°')
        if per_crystal_type:
            if sig_idl_separate:
                print(f'Spatial phase range of SPDCs (signal): 'f'{phase_range_deg(self.spatial_walkoff_s_spdcs):.1f}°')
                print(f'Spatial phase range of SPDCs (idler): 'f'{phase_range_deg(self.spatial_walkoff_i_spdcs):.1f}°')
                print(f'Spatial phase range of SCCs (signal): 'f'{phase_range_deg(self.spatial_walkoff_s_sccs):.1f}°')
                print(f'Spatial phase range of SCCs (idler): 'f'{phase_range_deg(self.spatial_walkoff_i_sccs):.1f}°')
            print(f'Spatial phase range of SPDCs: '
                  f'{phase_range_deg(self.spatial_walkoff_s_spdcs+self.spatial_walkoff_i_spdcs):.1f}°')
            print(f'Spatial phase range of SCCs: '
                  f'{phase_range_deg(self.spatial_walkoff_s_sccs+self.spatial_walkoff_i_sccs):.1f}°')
        if per_crystal:
            for crystal in self.spdcs:
                print(f'Spatial phase range of signal in {crystal.cname} (SPDC): '
                      f'{phase_range_deg(crystal.s_walkoff_signal):.1f}°')
                print(f'Spatial phase range of idler in {crystal.cname} (SPDC): '
                      f'{phase_range_deg(crystal.s_walkoff_idler):.1f}°')
            for crystal in self.signal_sccs + self.idler_sccs:
                print(f'Spatial phase range in {crystal.cname}: {phase_range_deg(crystal.s_walkoff):.1f}°')
        print('---------------------------------------------------------')

    def plot_spatial_walkoff_summary(self, per_crystal_type: bool = True, sig_idl_separate: bool = False,
                                     show_now: bool = False, show_tcc: bool = False,
                                     norm2center: str = 'none', export = False) -> list[plt.figure]:
        """
        Plots the phasemap of total spatial walk-off at the detector aperture plane. More details optional:

        :param per_crystal_type:    Also show phasemaps for each crystal type (default: True).
        :param sig_idl_separate:    Show requested phasemaps separately for signal and idler, otherwise show their sum
                                    (default: False)
        :param show_now:            Show plots immediately at end of method. Code execution halts until plot windows are
                                    closed (default: False).
        :param show_tcc:            Show plots for TCCs as well (default: False).
        :param norm2center:         Whether to subtract a flat phase offset (value of center ray) from certain plots.
                                    Possible values ['all', 'system', 'not_system', 'none' (default)].
        :param export:              Whether to export the plot data to csv file.
        :return:                    List of pyplot Figures.
        """
        # ensure that calculation has been run already, by checking presence of results
        if not hasattr(self,'spatial_phases') or self.spatial_phases is None:
            self.sum_spatial_walkoffs()
        figs = []
        if sig_idl_separate:
            figs.append(quickplot(self.spatial_walkoff_signal, r'$\Phi_\mathrm{signal,system} (°)$',
                                  norm2center=norm2center in ['all','system'], export=export,
                                  export_name = f'{self.csname}_signal-system'))
            figs.append(quickplot(self.spatial_walkoff_idler, r'$\Phi_\mathrm{idler,system} (°)$',
                                  norm2center=norm2center in ['all','system'], export=export,
                                  export_name = f'{self.csname}_idler-system'))
            if per_crystal_type:
                figs.append(quickplot(self.spatial_walkoff_s_spdcs, r'$\Phi_\mathrm{signal, SPDCs} (°)$',
                                      norm2center=norm2center in ['all','not_system'], export=export,
                                  export_name = f'{self.csname}_signal-SPDCs'))
                figs.append(quickplot(self.spatial_walkoff_i_spdcs, r'$\Phi_\mathrm{idler, SPDCs} (°)$',
                                      norm2center=norm2center in ['all','not_system'], export=export,
                                  export_name = f'{self.csname}_idler-SPDCs'))
                figs.append(quickplot(self.spatial_walkoff_s_sccs, r'$\Phi_\mathrm{signal, SCCs} (°)$',
                                      norm2center=norm2center in ['all','not_system'], export=export,
                                  export_name = f'{self.csname}_signal-SCCs'))
                figs.append(quickplot(self.spatial_walkoff_i_sccs, r'$\Phi_\mathrm{idler, SCCs} (°)$',
                                      norm2center=norm2center in ['all','not_system'], export=export,
                                  export_name = f'{self.csname}_idler-SCCs'))
            if show_tcc:
                figs.append(quickplot(self.spatial_walkoff_s_tccs, r'$\Phi_\mathrm{signal, TCCs} (°)$',
                                      norm2center=norm2center in ['all','not_system'], export=export,
                                  export_name = f'{self.csname}_signal-TCCs'))
        else:
            figs.append(quickplot(self.spatial_walkoff_total, r'$\Phi_\mathrm{total,system} (°)$',
                                  norm2center=norm2center in ['all','system'], export=export,
                                  export_name = f'{self.csname}_total-system'))
            if per_crystal_type:
                figs.append(quickplot(self.spatial_walkoff_s_spdcs+self.spatial_walkoff_i_spdcs,
                          r'$\Phi_\mathrm{total, SPDCs} (°)$', norm2center=norm2center in ['all','not_system'],
                                      export=export, export_name = f'{self.csname}_total-SPDCs'))
                figs.append(quickplot(self.spatial_walkoff_s_sccs+self.spatial_walkoff_i_sccs,
                          r'$\Phi_\mathrm{total, SCCs} (°)$', norm2center=norm2center in ['all','not_system'],
                                      export=export, export_name = f'{self.csname}_total-SCCs'))
            if show_tcc:
                figs.append(quickplot(2*self.spatial_walkoff_s_tccs, r'$\Phi_\mathrm{total, TCCs} (°)$',
                                      norm2center=norm2center in ['all','not_system'],
                                      export=export, export_name = f'{self.csname}_total-TCCs'))
        for fig in figs:
            fig.suptitle(f'{self.csname}')
        if show_now:
            print('Waiting for plot windows to be closed...')
            plt.show()
        return figs

    def plot_axes_overview(self, plot_beams: bool = True, plot_OAs: bool = True, show_now: bool = False) -> plt.figure:
        """
        Plot an overview over all crystal axes and the beams (outside of crystals).
        :param plot_beams:      Show beams (default: True).
        :param plot_OAs:        Show optical axes of crystals (default: True).
        :param show_now:        Show plots immediately at end of method. Code execution halts until plot windows are
                                closed (default: False).
        :return:                Pyplot Figure reference.
        """
        fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
        fig.suptitle(f'{self.csname}')
        ax.set_xlabel('x up/down')
        ax.set_ylabel('y left/right')
        ax.set_zlabel('z close/far')
        spdc_offset = len(self.spdcs) * 0.5
        tcc_offset = 1 + len(self.tccs) * 1.5 + spdc_offset
        scc_offset = 1 + len(self.signal_sccs) * 1.5 + spdc_offset
        if plot_beams:
            ax.quiver(*(-self.k_p[cidxlin,:] * tcc_offset), *self.k_p[cidxlin,:], length=tcc_offset+spdc_offset,
                      arrow_length_ratio=0, color='blue', linestyle='--', linewidth=0.5)
            for idx, spdc in enumerate(self.spdcs):
                # center pos of axis along k_p: const. offset + index dependent pos + center pos offset
                pos = (-spdc_offset + idx * 1 + 0.5) * self.k_p[cidxlin,:]
                ax.quiver(*pos, *self.k_signal[cidxlin,:], length=scc_offset, arrow_length_ratio=0, color='red',
                          linestyle='--', linewidth=0.5)
                ax.quiver(*pos, *self.k_idler[cidxlin,:], length=scc_offset, arrow_length_ratio=0, color='red',
                          linestyle='--', linewidth=0.5)
        if plot_OAs:
            for idx, tcc in enumerate(self.tccs):
                # center pos of axis along k_p: const. offset + index dependent pos + center pos offset
                pos = (-tcc_offset + 1 + idx * 1.5 + 0.75) * self.k_p[cidxlin,:]
                pos -= tcc.v_oa / 2  # center offset for optical axis itself
                ax.quiver(*pos, *tcc.v_oa, length=1, arrow_length_ratio=0, color='black')
            for idx, spdc in enumerate(self.spdcs):
                # center pos of axis along k_p: const. offset + index dependent pos + center pos offset
                pos = (-spdc_offset + idx * 1 + 0.5) * self.k_p[cidxlin,:]
                pos -= spdc.v_oa / 2  # center offset for optical axis itself
                ax.quiver(*pos, *spdc.v_oa, length=1, arrow_length_ratio=0, color='black')
            for k_beam, sccs in zip([self.k_signal,self.k_idler],[self.signal_sccs,self.idler_sccs]):
                for idx, scc in enumerate(sccs):
                    # center pos of axis along k_beam: const. offset + index dependent pos + center pos offset
                    pos = (1 + idx * 1 + 0.5) * k_beam[cidxlin,:]
                    pos -= scc.v_oa / 4  # center offset for optical axis itself
                    ax.quiver(*pos, *scc.v_oa/2, length=1, arrow_length_ratio=0, color='black')
        # axis limits must be equal, if angles are to be displayed without distortion:
        ax.set_xlim([-tcc_offset, scc_offset])
        ax.set_ylim([-tcc_offset, scc_offset])
        ax.set_zlim([-tcc_offset, scc_offset])
        ax.view_init(vertical_axis='x')
        if show_now:
            plt.show()
        return fig

    def plot_pol_angles(self, show_pols: Union[list[str], str] = None, show_now: bool = False) -> list[plt.figure]:
        """
        Plot the polarization angles of the signal and idler beams.
        :param show_pols:            List of nominal polarizations to show (possible arguments: ['H', 'V'];
                                    default: both)
        :param show_now:            Show plots immediately at end of method. Code execution halts until plot windows are
                                    closed (default: False).
        :return:                    List of pyplot Figures.
        """
        # First we need to define a proper reference vector to compare against. For this, we use the pol_V vector
        # rotated from k_p to the corresponding k_beam ray:
        if show_pols is None:
            show_pols = ['V', 'H']
        figs = []
        for beam in ['signal', 'idler']:
            for p, pol_label in enumerate(['V', 'H']):
                if pol_label in show_pols:
                    fig = quickplot(data = vecangle(self.polarizations[beam][p], self.ref_pol_vecs[beam]),
                                    zlabel = rf'$\varphi_\mathrm{{{beam:s}, {pol_label:s}}} (°)$')  # double curly to escape f-string
                    fig.suptitle(f'{self.csname}')
                    figs.append(fig)
        if show_now:
            plt.show()
        return figs


def quickplot(data: np.array, zlabel: str, norm2center: bool = False, kwiat_style: bool = False,
              export: bool = False, export_name: str = "exported_plot") -> plt.figure:
    """
    Helper function to show angular values of the ray fields with consistent style. ToDo: Could be refactored with more
    options for even more multipurpose use and less dependence on global constants.

    :param data:            Expects a 1D numpy array of angular values in radians (same format as the phasemaps
                            calculated by the CrystalSystem class).
    :param zlabel:          Label string to for the value axis.
    :param norm2center:     Whether to automatically subtract a constant offset (value of central ray) (default: False).
    :param kwiat_style:     Selects some predefined axis properties to mimic plots as shown in Ref. [1].
    :param export:          Whether to export the figure as csv file.
    :param export_name:     Filename for exported file.
    :return:                Pyplot Figure reference.
    """
    fig, ax = plt.subplots(subplot_kw={"projection": "3d"})  # new figure with 3d axes
    # coordinate grid at detector aperture (not nice: uses constants, defined at top of module):
    x, y = np.meshgrid(a_d, a_d)
    # convert coordinates from meters to mm, have angle-array be converted to proper format and plot as a surface plot
    surf = ax.plot_surface(x*1e3, y*1e3, dispangle(data, norm2center=norm2center), cmap=cm.coolwarm)
    # set axis labels:
    ax.set_xlabel('x (mm) up/down')
    ax.set_ylabel('y (mm) left/right')
    ax.set_zlabel(zlabel)
    # if requested configure axes limits, ticks and directions
    if kwiat_style:
        ax.set_xlim([-5, 5])
        ax.set_ylim([-5, 5])
        ax.set_zlim([-120, 120])
        ax.set_zticks([-90, 0, 90])
        ax.zaxis.set_minor_locator(AutoMinorLocator(3))
        ax.invert_yaxis()
        ax.invert_zaxis()
    # add a colorbar next to 3D plot:
    # fig.colorbar(surf)
    if export:
        data_with_axes = np.concatenate((a_d * 1e3, dispangle(data, norm2center=norm2center)))
        y_col_plus_empty = np.concatenate((np.array([[np.nan]]),a_d * 1e3), axis=1).T
        data_with_axes = np.concatenate((y_col_plus_empty, data_with_axes), axis=1)
        if '.csv' not in export_name:
            export_name = f'{export_name}.csv'
        np.savetxt(export_name, data_with_axes, delimiter=",",
                   header="First line/column: Position in mm; Array: Phase/Angle in degrees.")
    return fig


def dispangle(array: np.array, norm2center: bool = False) -> np.array:
    """
    Helper function to convert 1D numpy array of angular values in radians to a 2D array (in degrees).
    :param array:           Expects a 1D numpy array of angular values in radians (same format as the phasemaps
                            calculated by the CrystalSystem class).
    :param norm2center:     Whether to automatically subtract a constant offset (value of central ray) (default: False).
    :return:                2D numpy array of angular values in degrees.
    """
    temp = np.reshape(np.rad2deg(array), (points,points))
    if norm2center:
        temp = temp - temp[cidx,cidx]
    return temp


def phase_range_deg(phasemap: np.array, circ_aperture: bool = True) -> float:
    """
    Get the min to max range of the input numpy array and convert radians to degrees
    :param phasemap:        Expects a numpy array of angular values in radians
    :param circ_aperture:   Restrict evaluation to circular aperture, instead of quadratic ray field (default: True)
    :return:                min to max range in degrees
    """
    if circ_aperture:
        # calculate normed distance from center (in range [-1,1]) along one axis:
        dist = np.expand_dims(np.arange(points)-cidx, 0)/cidx
        x_dist, y_dist = np.meshgrid(dist, dist.T)  # build distance grid
        radial_dist = np.sqrt(x_dist**2 + y_dist**2).reshape(-1, 1)  # calculate radial distance and flatten to 1D array
        phasemap = phasemap[radial_dist < 1]  # filter phasemap for values inside the circular aperture
    return np.rad2deg(np.max(phasemap)-np.min(phasemap))


def listdot(v1: np.array, v2: np.array) -> np.array:
    """
    Calculates vector dot products (with proper array shape) if at least one input is a 'list' of vectors (as 2D numpy
    array).

    :param v1:  Expects vector list as 2D numpy array, where the first dimension indices the vectors (arbitrary length)
                in the second dimension. One input may also be a 1D numpy array of a single vector.
    :param v2:  Same as v1. Vector lengths must match. If both inputs are vector lists, the sizes must match as well.
    :return:    List of dot products as 2D numpy array. Keeps original dimensions for proper broadcasting later on, but
                second dimension is singular.
    """
    if v1.size == v2.size:
        # see: https://stackoverflow.com/questions/37670658/python-dot-product-of-each-vector-in-two-lists-of-vectors
        return np.einsum('ij, ij ->i', v1, v2)[:, np.newaxis]
        # explicit, slower alternative:
        # return np.array([np.dot(a,b) for (a,b) in zip(list(v1), list(v2))])[:,np.newaxis]
    if v2.ndim == 1 and v1.ndim == 2:
        v2 = v2[np.newaxis]  # add dimension for proper transpose and broadcasting in np.dot
        return np.dot(v1, v2.T)
    elif v1.ndim == 1 and v2.ndim == 2:
        v1 = v1[np.newaxis]  # add dimension for proper transpose and broadcasting in np.dot
        return np.dot(v2, v1.T)  # flip vectors to keep proper array dimensions after "matrix"-vector-dot-product
    else:
        raise ValueError('Vector lists must have equal length.')  # this is an assumption of the most likely error!


def vecangle(v1: np.array, v2: np.array) -> Union[np.array, float]:
    """
    Calculates angle between both input vectors (with proper array shape). Both inputs may also be a 'list' of vectors
    (as 2D numpy array).

    :param v1:  Expects vector list as 2D numpy array, where the first dimension indices the vectors (arbitrary length)
                in the second dimension. Both inputs may also be a 1D numpy array of a single vector.
    :param v2:  Same as v1. Vector lengths must match. If both inputs are vector lists, the sizes must match as well.
    :return:    List of angles (rad) as 2D numpy array. Keeps original dimensions for proper broadcasting later on, but
                second dimension is singular. If both inputs are single vectors in 1D array, return type is a scalar.
    """
    if v1.ndim == 1 and v2.ndim == 1:
        angle = np.arccos(np.dot(v1, v2)/np.linalg.norm(v1)/np.linalg.norm(v2))
    elif v1.ndim == 2 and v2.ndim == 2:
        angle = np.arccos(listdot(v1, v2)/np.linalg.norm(v1, axis=1, keepdims=True)/np.linalg.norm(v2, axis=1, keepdims=True))
    else:
        if v2.ndim == 1:
            v2 = v2[np.newaxis]
        if v1.ndim == 1:
            v1 = v1[np.newaxis]
            v1, v2 = (v2, v1)  # flip vectors to keep proper array dimensions after "matrix"-vector-dot-product
        angle = np.arccos(np.dot(v1, v2.T)/np.linalg.norm(v1, axis=1, keepdims=True)/np.linalg.norm(v2, axis=1, keepdims=True))
    # numerical issues can result in normed vector product of identical vectors
    # to be epsilon larger than 1 causing NaNs --> replace with correct zero:
    return np.where(np.isnan(angle), 0, angle)


# ______________________________ END of module definitions (main function follows below) _______________________________

# ----------------------------------- Some definitions for Thorlabs EDU-QOPA1 setup: -----------------------------------
default_detector = {'hoa': 3, 'r_aperture': 5e-3, 'distance': 1.0, 'points': points, 'bandwidth': 10e-9}
default_wl = {'pump': 405e-9, 'pump_bw': 0.5e-9}
pol_vecs_ideal = {'pump': [pol_H, pol_V], 'signal': [pol_V, pol_H], 'idler': [pol_V, pol_H]}
pol_vecs_type2 = {'pump': [pol_V, pol_V], 'signal': [pol_V, pol_H], 'idler': [pol_H, pol_V]}

design_thickness = 1.2e-3
# Note that the TCC crystal thickness has been optimized from experimental results and is thinner than the optimal value
# calculated here.
QOPA1_TCC = Crystal('TCC', 'BBO', 0.71 * design_thickness, cutangle_ud = 80, tiltangle_ud= 0)
QOPA1_SPDC = Crystal('SPDC-1', 'BBO', design_thickness, cutangle_lr = 29.2)
QOPA1_SCC = Crystal('SCC-signal', 'BBO', design_thickness, cutangle_lr = -12.7, tiltangle_lr = 3)
EDU_QOPA1_Setup = CrystalSystem('EDU-QOPA1', default_wl, default_detector,
                                             [QOPA1_TCC],[QOPA1_SPDC, QOPA1_SPDC.copy('SPDC-2',90)],
                                             [QOPA1_SCC], [QOPA1_SCC.copy('dSCC-idler',180,True)])

# ------------------- For comparision with Ref. [1] -------------------
Kwiat_pair = Crystal('SPDC-1', 'BBO', 0.6e-3, cutangle_lr = 33.9)
Kwiat_scomp = Crystal('sComp_signal', 'BBO', 0.245e-3, cutangle_lr= 33.9, tiltangle_lr= 0)
Kwiat_system = CrystalSystem('Kwiat_system', {'pump': 351e-9},default_detector,[],
                             [Kwiat_pair, Kwiat_pair.copy('SPDC-2', 90)],[Kwiat_scomp],
                             [Kwiat_scomp.copy('sComp_idler', 180, True)])

# --------------- additional Crystals (Thorlabs catalog) --------------
Dummy = Crystal('Dummy', 'Quartz', 0, cutangle_ud=90)  # zero thickness dummy crystal -> does nothing

# https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_ID=15444
NLC01 = Crystal('NLC03', 'BBO', 0.15e-3, cutangle_ud = 30.5)
NLC02 = Crystal('NLC03', 'BBO', 0.30e-3, cutangle_ud = 30.5)
NLC03 = Crystal('NLC03', 'BBO', 0.60e-3, cutangle_ud = 30.5)

NLC04 = Crystal('NLC04', 'BBO', 0.5e-3, cutangle_ud = 23.3)
NLC05 = Crystal('NLC04', 'BBO', 1.0e-3, cutangle_ud = 23.3)
NLC06 = Crystal('NLC04', 'BBO', 2.0e-3, cutangle_ud = 23.3)

NLC07 = Crystal('NLC07', 'BBO', 3.0e-3, cutangle_ud = 19.8)

NLC08 = Crystal('NLC07', 'BBO', 30e-6, cutangle_ud = 29.2)
NLC09 = Crystal('NLC07', 'BBO', 75e-6, cutangle_ud = 29.2)

# https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=16384
NLCQ1 = Crystal('SPDC', 'BBO', 1e-3, cutangle_ud = 29.2)
NLCQ2 = Crystal('SPDC', 'BBO', 2e-3, cutangle_ud = 29.2)
NLCQ3 = Crystal('SPDC', 'BBO', 3e-3, cutangle_ud = 29.2)

NLCQ4 = Crystal('SPDC', 'BBO', 1e-3, cutangle_ud = 41.8)
NLCQ5 = Crystal('SPDC', 'BBO', 2e-3, cutangle_ud = 41.8)
NLCQ6 = Crystal('SPDC', 'BBO', 3e-3, cutangle_ud = 41.8)

NLCQ7 = Crystal('SPDC', 'BBO', 3e-3, cutangle_ud = 26.9)
NLCQ8 = Crystal('SPDC', 'BBO', 3e-3, cutangle_ud = 22.2)
NLCQ9 = Crystal('SPDC', 'BBO', 3e-3, cutangle_ud = 19.8)

# --------------------- Test of Type-II SPDC ---------------------
# Note: All walk-offs calculated for a nominally perfect compensation system with NLCQ5 and NLCQ4 are exactly zero.
# However, the calculation doesn't take in account imperfections of the polarization flip by the half-waveplate required
# between SPDC and SCC crystal, as well as other polarization distorting effects. In reality, there still may be quite
# a lot of walk-off in the system. The calculation can still help to find additional promising candidates for
# compensation crystals.
# Type2_system = CrystalSystem('Type-II System', default_wl, default_detector,
#                             tccs=[Dummy], spdcs=[NLCQ5],
#                             signal_sccs=[NLCQ4], idler_sccs=[NLCQ4.copy('comp-idler')],
#                             beam_polarizations=pol_vecs_type2, spdc_type=2)

if __name__ == '__main__':
    # Start out by plotting refractive indices comparison between different parameter sources.
    bBBO_NLP = Crystal('beta-BBO','beta-BBO',0)
    bBBO_THO = Crystal('beta-BBO-T','beta-BBO-T',0)
    wl = np.arange(350e-9, 850e-9, 10e-9)
    (n_o_NLP, n_e_NLP, *_) = bBBO_NLP.get_ref_indices(wl)
    (n_o_THO, n_e_THO, *_) = bBBO_THO.get_ref_indices(wl)
    fig, ax = plt.subplots()
    fig.suptitle('Refractive indices comparison between parameter sources')
    ax.plot(wl*1e9,n_o_NLP, color='black', label='$n_o$ (Newlight Photonics)')
    ax.plot(wl*1e9,n_e_NLP, color='black', linestyle='--', label='$n_e$ (Newlight Photonics)')
    ax.plot(wl*1e9,n_o_THO, color='red', label='$n_o$ (Thorlabs)')
    ax.plot(wl*1e9,n_e_THO, color='red', linestyle='--', label='$n_e$ (Thorlabs)')
    ax.set_xlabel('wavelength (nm)')
    ax.set_ylabel('ref. index')
    ax.legend(loc='center right')

    # Plot refractive and group indices relevant for the SPDC crystals of EDU-QOP(A)1.
    BBO = Crystal('BBO', 'BBO', 0)
    wl = np.arange(405e-9, 810e-9, 10e-9)
    (n_o, n_e, n_eff, g_o, g_e, g_eff, *_) = BBO.get_ref_indices(wl)
    fig, ax = plt.subplots()
    fig.suptitle('Refractive indices SPDC EDU-QOP(A)1')
    ax.plot(wl * 1e9, n_o, color='black', label='$n_o$')
    ax.plot(wl * 1e9, n_e, color='red', linestyle='--', label='$n_e$')
    ax.plot(wl * 1e9, n_eff(np.deg2rad(29.2)), color='red', label='$n_{eff} (29.2°)$')
    ax.set_xlabel('wavelength (nm)')
    ax.set_ylabel('ref. index')
    ax.grid()
    ax.legend(loc='center left')
    fig, ax = plt.subplots()
    fig.suptitle('Group indices SPDC EDU-QOP(A)1')
    ax.plot(wl * 1e9, g_o, color='black', label='$g_o$')
    ax.plot(wl * 1e9, g_e, color='red', linestyle='--', label='$g_e$')
    ax.plot(wl * 1e9, g_eff(np.deg2rad(29.2)), color='red', label='$g_{eff} (29.2°)$')
    ax.set_xlabel('wavelength (nm)')
    ax.set_ylabel('group index')
    ax.legend()

    for system in [EDU_QOPA1_Setup]:
        print(f'Report for crystal system "{system}":')
        system.plot_axes_overview()
        system.print_temp_walkoff_summary(per_crystal_type=True, advice=True)
        system.print_spatial_walkoff_summary(per_crystal_type=False, per_crystal=False, sig_idl_separate=False)
        system.print_tcc_phase_and_displacement_summary()
        system.plot_spatial_walkoff_summary(sig_idl_separate=False, per_crystal_type=True, norm2center='all',
                                            show_tcc=False, show_now=False, export=False)
        # system.plot_pol_angles('H')  # after pol-refinement
        print('______________________________________________________________')
    plt.show()

