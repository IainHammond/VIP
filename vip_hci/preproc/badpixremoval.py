#! /usr/bin/env python

"""
Module with functions for correcting bad pixels in cubes.
"""



__author__ = 'Carlos Alberto Gomez Gonzalez, V. Christiaens'
__all__ = ['frame_fix_badpix_isolated',
           'cube_fix_badpix_isolated',
           'cube_fix_badpix_annuli',
           'cube_fix_badpix_clump']

import numpy as np
from skimage.draw import circle, ellipse
from scipy.ndimage import median_filter
from astropy.stats import sigma_clipped_stats
from ..stats import sigma_filter
from ..var import frame_center, get_annulus_segments
from ..stats import clip_array
from ..conf import timing, time_ini, Progressbar
from .cosmetics import approx_stellar_position

import warnings
try:
    from numba import njit
    no_numba = False
except ImportError:
    msg = "Numba python bindings are missing."
    warnings.warn(msg, ImportWarning)
    no_numba = True

def frame_fix_badpix_isolated(array, bpm_mask=None, sigma_clip=3, num_neig=5,
                              size=5, protect_mask=False, radius=30,
                              verbose=True):
    """ Corrects the bad pixels, marked in the bad pixel mask. The bad pixel is
     replaced by the median of the adjacent pixels. This function is very fast
     but works only with isolated (sparse) pixels.

     Parameters
     ----------
     array : numpy ndarray
         Input 2d array.
     bpm_mask : numpy ndarray, optional
         Input bad pixel map. Zeros frame where the bad pixels have a value of
         1. If None is provided a bad pixel map will be created using
         sigma clip statistics. 
     sigma_clip : int, optional
         In case no bad pixel mask is provided all the pixels above and below
         sigma_clip*STDDEV will be marked as bad.
     num_neig : int, optional
         The side of the square window around each pixel where the sigma clipped
         statistics are calculated (STDDEV and MEDIAN). If the value is equal to
         0 then the statistics are computed in the whole frame.
     size : odd int, optional
         The size the box (size x size) of adjacent pixels for the median
         filter.
     protect_mask : bool, optional
         If True a circular aperture at the center of the frames will be
         protected from any operation. With this we protect the star and
         vicinity.
     radius : int, optional
         Radius of the circular aperture (at the center of the frames) for the
         protection mask.
     verbose : bool, optional
         If True additional information will be printed.

     Return
     ------
     frame : numpy ndarray
         Frame with bad pixels corrected.
     """
    if array.ndim != 2:
        raise TypeError('Array is not a 2d array or single frame')
    if size % 2 == 0:
        raise TypeError('Size of the median blur kernel must be an odd integer')

    if bpm_mask is not None:
        bpm_mask = bpm_mask.astype('bool')

    if verbose:  start = time_ini()

    if num_neig > 0:
        neigh = True
    else:
        neigh = False

    frame = array.copy()
    cy, cx = frame_center(frame)
    if bpm_mask is None:
        ind = clip_array(frame, sigma_clip, sigma_clip, neighbor=neigh,
                         num_neighbor=num_neig, mad=True)
        bpm_mask = np.zeros_like(frame)
        bpm_mask[ind] = 1
        if protect_mask:
            cir = circle(cy, cx, radius)
            bpm_mask[cir] = 0
        bpm_mask = bpm_mask.astype('bool')

    smoothed = median_filter(frame, size, mode='mirror')
    frame[np.where(bpm_mask)] = smoothed[np.where(bpm_mask)]
    array_out = frame
    count_bp = np.sum(bpm_mask)
    
    if verbose:
        msg = "/nDone replacing {} bad pixels using the median of neighbors"
        print(msg.format(count_bp))
        timing(start)
    return array_out


def cube_fix_badpix_isolated(array, bpm_mask=None, sigma_clip=3, num_neig=5, 
                             size=5, frame_by_frame=False, protect_mask=False, 
                             radius=30, verbose=True):
    """ Corrects the bad pixels, marked in the bad pixel mask. The bad pixel is 
    replaced by the median of the adjacent pixels. This function is very fast
    but works only with isolated (sparse) pixels. 
     
    Parameters
    ----------
    array : numpy ndarray
        Input 3d array.
    bpm_mask : numpy ndarray, optional
        Input bad pixel map. Zeros frame where the bad pixels have a value of 1.
        If None is provided a bad pixel map will be created per frame using 
        sigma clip statistics.
    sigma_clip : int, optional
        In case no bad pixel mask is provided all the pixels above and below
        sigma_clip*STDDEV will be marked as bad. 
    num_neig : int, optional
        The side of the square window around each pixel where the sigma clipped
        statistics are calculated (STDDEV and MEDIAN). If the value is equal to
        0 then the statistics are computed in the whole frame.
    size : odd int, optional
        The size the box (size x size) of adjacent pixels for the median filter. 
    frame_by_frame: bool, optional
        Whether to correct bad pixels frame by frame in the cube. By default it
        is set to False; the bad pixels are computed on the mean frame of the 
        stack (faster but not necessarily optimal).
    protect_mask : bool, optional
        If True a circular aperture at the center of the frames will be 
        protected from any operation. With this we protect the star and its
        vicinity.
    radius : int, optional 
        Radius of the circular aperture (at the center of the frames) for the 
        protection mask.
    verbose : bool, optional
        If True additional information will be printed.
    
    Return
    ------
    array_out : numpy ndarray
        Cube with bad pixels corrected.
    """
    if array.ndim != 3:
        raise TypeError('Array is not a 3d array or cube')
    if size % 2 == 0:
        raise TypeError('Size of the median blur kernel must be an odd integer')
    
    if bpm_mask is not None:
        bpm_mask = bpm_mask.astype('bool')
    
    if verbose:  start = time_ini()
    
    if num_neig > 0:
        neigh = True
    else:
        neigh = False
    
    cy, cx = frame_center(array[0])
    array_out = array.copy()
    n_frames = array.shape[0]
    count_bp = 0
    if frame_by_frame:
        for i in Progressbar(range(n_frames), desc="processing frames"):
            array_out[i] = frame_fix_badpix_isolated(array[i], bpm_mask=bpm_mask, 
                                                    sigma_clip=sigma_clip, 
                                                    num_neig=num_neig,
                                                    size=size, 
                                                    protect_mask=protect_mask, 
                                                    radius=radius,
                                                    verbose=False,
                                                    debug=False)
            if verbose:                                       
                bpm = np.where(array_out[i]!=array[i])   
                count_bp+=np.sum(np.ones_like(array_out[i])[bpm])                                   
    else:                                                
        if bpm_mask is None:
            ind = clip_array(np.mean(array, axis=0), sigma_clip, sigma_clip,
                             neighbor=neigh, num_neighbor=num_neig, mad=True)
            bpm_mask = np.zeros_like(array[0])
            bpm_mask[ind] = 1
            if protect_mask:
                cir = circle(cy, cx, radius)
                bpm_mask[cir] = 0
            bpm_mask = bpm_mask.astype('bool')
    
        for i in Progressbar(range(n_frames), desc="processing frames"):
            frame = array_out[i]
            smoothed = median_filter(frame, size, mode='mirror')
            frame[np.where(bpm_mask)] = smoothed[np.where(bpm_mask)]
            if verbose: 
                count_bp+=np.sum(bpm_mask)  
            
    if verbose: 
        msg = "/nDone replacing {} bad pixels using the median of neighbors"
        print(msg.format(count_bp))
        timing(start)
    return array_out


def cube_fix_badpix_annuli(array, fwhm, cy=None, cx=None, sig=5., 
                           protect_psf=True, r_in_std=10, r_out_std=None, 
                           verbose=True, half_res_y=False, min_thr=None, 
                           max_thr=None, full_output=False):
    """
    Function to correct the bad pixels annulus per annulus (centered on the 
    provided location of the star), in an input frame or cube.
    This function is MUCH FASTER than bp_clump_removal (about 20 times faster);
    hence to be prefered in all cases where there is only one bright source.
    The bad pixel values are replaced by: ann_median + ann_stddev*random_gauss;
    where ann_median is the median of the annulus, ann_stddev is the standard 
    deviation in the annulus, and random_gauss is a random factor picked from a 
    gaussian distribution centered on 0 and with variance 1.

    Parameters
    ----------
    array : 3D or 2D array 
        Input 3d cube or 2d image.
    fwhm: float or 1D array
        Vector containing the full width half maximum of the PSF in pixels, for 
        each channel (cube_like); or single value (frame_like)
    cy, cx : None, float or 1D array, optional
        If None: will use the barycentre of the image found by 
        photutils.centroid_com()
        If floats: coordinates of the center, assumed to be the same in all 
        frames if the input is a cube.
        If 1D arrays: they must be the same length as the 0th dimension of the
        input cube.
    sig: Float scalar, optional
        Number of stddev above or below the median of the pixels in the same 
        annulus, to consider a pixel as bad.
    protect_psf: bool, {True, False}, optional
        Whether to protect a circular region centered on the star (1.8*fwhm 
        radius) from any bpix corr. If False, there is a risk of modifying a 
        centroid peak value if it is too "peaky"; but if True real bad pixels 
        within the core are not corrected.
    r_in_std: float, optional
        Inner radius in fwhm for the calculation of the standard 
        deviation of the background - used for min threshold 
        to consider bad pixels. Default: 10 FWHM.
    r_out_std: float or None, optional
        Outer radius in fwhm for the calculation of the standard 
        deviation of the background - used for min threshold 
        to consider bad pixels. If set to None, the default will be to 
        consider the largest annulus that fits within the frame.
    verbose: bool, {False, True}, optional
        Whether to print out the number of bad pixels in each frame. 
    half_res_y: bool, {True,False}, optional
        Whether the input data have only half the angular resolution vertically 
        compared to horizontally (e.g. SINFONI data).
        The algorithm will then correct the bad pixels every other row.
    min_thr, max_thr: {None,float}, optional
        Any pixel whose value is lower (resp. larger) than this threshold will 
        be automatically considered bad and hence sigma_filtered. If None, it 
        is not used.
    full_output: bool, {False,True}, optional
        Whether to return as well the cube of bad pixel maps and the cube of 
        defined annuli.

    Returns:
    --------
    obj_tmp: 2d or 3d array; the bad pixel corrected frame/cube.
    If full_output is set to True, it returns as well:
    bpix_map: 2d or 3d array; the bad pixel map or the cube of bpix maps
    ann_frame_cumul: 2 or 3d array; the cube of defined annuli
    """

    obj_tmp = array.copy()
    ndims = obj_tmp.ndim
    assert ndims == 2 or ndims == 3, "Object is not two or three dimensional.\n"

    #thresholds
    if min_thr is None:
        min_thr = np.amin(obj_tmp)-1
    if max_thr is None:
        max_thr = np.amax(obj_tmp)-1

    def bp_removal_2d(obj_tmp, cy, cx, fwhm, sig, protect_psf, r_in_std,
                      r_out_std, verbose):

        n_x = obj_tmp.shape[1]
        n_y = obj_tmp.shape[0]

        # Squash the frame if twice less resolved vertically than horizontally
        if half_res_y:
            if n_y % 2 != 0:
                msg = 'The input frames do not have of an even number of rows. '
                msg2 = 'Hence, you should not use option half_res_y = True'
                raise ValueError(msg+msg2)
            n_y = int(n_y/2)
            cy = int(cy/2)
            frame = obj_tmp.copy()
            obj_tmp = np.zeros([n_y,n_x])
            for yy in range(n_y):
                obj_tmp[yy] = frame[2*yy]

        #1/ Stddev of background 
        if r_in_std or r_out_std:
            r_in_std = min(r_in_std*fwhm,cx-2, cy-2,n_x-cx-2,n_y-cy-2)
            if r_out_std:
                r_out_std *= fwhm
            else:
                r_out_std = min(n_y-(cy+r_in_std), cy-r_in_std, 
                                n_x-(cx+r_in_std), cx-r_in_std)
            ceny, cenx = frame_center(obj_tmp)
            width = max(2,r_out_std-r_in_std)
            obj_tmp_crop = get_annulus_segments(obj_tmp, r_in_std, width, 
                                                mode="val")
        else:
            obj_tmp_crop = obj_tmp
        _, _, stddev = sigma_clipped_stats(obj_tmp_crop, sigma=2.5)

        #2/ Define each annulus, its median and stddev
        
        ymax = max(cy, n_y-cy)
        xmax = max(cx, n_x-cx)
        if half_res_y:
            ymax *= 2
        rmax = np.sqrt(ymax**2+xmax**2)
        # the annuli definition is optimized for Airy rings
        ann_width = max(1.5, 0.5*fwhm) #0.61*fwhm
        nrad = int(rmax/ann_width)+1
        d_bord_max = max(n_y-cy, cy, n_x-cx, cx)
        if half_res_y:
            d_bord_max = max(2*(n_y-cy), 2*cy, n_x-cx, cx)

        big_ell_frame = np.zeros_like(obj_tmp)
        sma_ell_frame = np.zeros_like(obj_tmp)
        ann_frame_cumul = np.zeros_like(obj_tmp)
        n_neig = np.zeros(nrad, dtype=np.int16)
        med_neig = np.zeros(nrad)
        std_neig = np.zeros(nrad)
        neighbours = np.zeros([nrad,n_y*n_x])

        for rr in range(nrad):
            if rr > int(d_bord_max/ann_width):
                # just to merge farthest annuli with very few elements 
                rr_big = nrad  
                rr_sma = int(d_bord_max/ann_width)
            else: 
                rr_big = rr
                rr_sma= rr
            if half_res_y:
                big_ell_idx = ellipse(cy=cy, cx=cx, 
                                      r_radius=((rr_big+1)*ann_width)/2, 
                                      c_radius=(rr_big+1)*ann_width, 
                                      shape=(n_y,n_x))
                if rr != 0:
                    small_ell_idx = ellipse(cy=cy, cx=cx, 
                                            r_radius=(rr_sma*ann_width)/2, 
                                            c_radius=rr_sma*ann_width, 
                                            shape=(n_y,n_x))
            else:
                big_ell_idx = circle(cy, cx, radius=(rr_big+1)*ann_width,
                                     shape=(n_y,n_x))
                if rr != 0:
                    small_ell_idx = circle(cy, cx, radius=rr_sma*ann_width, 
                                           shape=(n_y,n_x))
            big_ell_frame[big_ell_idx] = 1
            if rr!=0: sma_ell_frame[small_ell_idx] = 1
            ann_frame = big_ell_frame - sma_ell_frame
            n_neig[rr] = ann_frame[np.where(ann_frame)].shape[0]
            neighbours[rr,:n_neig[rr]] = obj_tmp[np.where(ann_frame)]
            ann_frame_cumul[np.where(ann_frame)] = rr

            # We delete iteratively max and min outliers in each annulus, 
            # so that the annuli median and stddev are not corrupted by bpixs
            neigh = neighbours[rr,:n_neig[rr]]
            n_rm = 0
            n_pix_init = neigh.shape[0]
            while neigh.shape[0] >= np.amin(n_neig[rr]) and n_rm < n_pix_init/5:
                min_neigh = np.amin(neigh)
                if reject_outliers(neigh, min_neigh, m=5, stddev=stddev):
                    min_idx = np.argmin(neigh)
                    neigh = np.delete(neigh,min_idx)
                    n_rm += 1
                else:
                    max_neigh = np.amax(neigh)
                    if reject_outliers(neigh, max_neigh, m=5, 
                                            stddev=stddev):
                        max_idx = np.argmax(neigh)
                        neigh = np.delete(neigh,max_idx)
                        n_rm += 1
                    else: break
            n_neig[rr] = neigh.shape[0]
            neighbours[rr,:n_neig[rr]] = neigh
            neighbours[rr,n_neig[rr]:] = 0
            med_neig[rr] = np.median(neigh)
            std_neig[rr] = np.std(neigh)
        
        #3/ Create a tuple-array with coordinates of a circle of radius 1.8*fwhm
        # centered on the provided coordinates of the star
        if protect_psf:
            if half_res_y: 
                circl_new = ellipse(cy, cx, r_radius=0.9*fwhm, 
                                    c_radius=1.8*fwhm, shape=(n_y,n_x))
            else: 
                circl_new = circle(cy, cx, radius=1.8*fwhm, 
                                   shape=(n_y, n_x))
        else: circl_new = []

        #4/ Loop on all pixels to check bpix
        bpix_map = np.zeros_like(obj_tmp)
        obj_tmp_corr = obj_tmp.copy()
        obj_tmp_corr, bpix_map = correct_ann_outliers(obj_tmp, ann_width, sig, 
                                                      med_neig, std_neig, cy, 
                                                      cx, min_thr, max_thr, 
                                                      stddev, half_res_y)

        #5/ Count bpix and uncorrect if within the circle
        nbpix_tot = np.sum(bpix_map)
        nbpix_tbc = nbpix_tot - np.sum(bpix_map[circl_new])
        bpix_map[circl_new] = 0
        obj_tmp_corr[circl_new] = obj_tmp[circl_new]
        if verbose:
            print(nbpix_tot, ' bpix in total, and ', nbpix_tbc, ' corrected.')

        # Unsquash all the frames
        if half_res_y:
            frame = obj_tmp_corr.copy()
            frame_bpix = bpix_map.copy()
            n_y = 2*n_y
            obj_tmp_corr = np.zeros([n_y,n_x])
            bpix_map = np.zeros([n_y,n_x])
            ann_frame = ann_frame_cumul.copy()
            ann_frame_cumul = np.zeros([n_y,n_x])
            for yy in range(n_y):
                obj_tmp_corr[yy] = frame[int(yy/2)]
                bpix_map[yy] = frame_bpix[int(yy/2)]
                ann_frame_cumul[yy] = ann_frame[int(yy/2)]

        return obj_tmp_corr, bpix_map, ann_frame_cumul



    if ndims == 2:
        if cy is None or cx is None:
            cen = approx_stellar_position([obj_tmp], fwhm)
            cy = cen[0,0]
            cx = cen[0,1]
        obj_tmp, bpix_map, ann_frame_cumul = bp_removal_2d(obj_tmp, cy, cx, 
                                                           fwhm, sig, 
                                                           protect_psf, 
                                                           r_in_std, r_out_std,
                                                           verbose)
    if ndims == 3:
        n_z = obj_tmp.shape[0]
        bpix_map = np.zeros_like(obj_tmp)
        ann_frame_cumul = np.zeros_like(obj_tmp)
        if isinstance(fwhm, (int,float)):
            fwhm = [fwhm]*n_z
        if cy is None or cx is None:
            cen = approx_stellar_position(obj_tmp, fwhm)
            cy = cen[:,0]
            cx = cen[:,1]
        elif isinstance(cy, (float,int)) and isinstance(cx, (float,int)): 
            cy = [cy]*n_z
            cx = [cx]*n_z
        for i in range(n_z):
            if verbose:
                print('************Frame # ', i,' *************')
                print('centroid assumed at coords:',cx[i],cy[i])    
            res_i = bp_removal_2d(obj_tmp[i], cy[i], cx[i], fwhm[i], sig,
                                  protect_psf, r_in_std, r_out_std, verbose)
            obj_tmp[i], bpix_map[i], ann_frame_cumul[i] = res_i
 
    if full_output:
        return obj_tmp, bpix_map, ann_frame_cumul
    else:
        return obj_tmp


def cube_fix_badpix_clump(array, bpm_mask=None, cy=None, cx=None, fwhm=4., 
                          sig=4., protect_psf=True, verbose=True, 
                          half_res_y=False, min_thr=None, max_nit=15, 
                          full_output=False):
    """
    Function to correct clumps of bad pixels. Very fast when a bad pixel map is 
    provided. If a bad pixel map is not provided, the bad pixel clumps will be 
    searched iteratively and replaced by the median of good neighbouring pixel 
    values if enough of them. The size of the box is set by the closest odd 
    integer larger than fwhm (to avoid accidentally replacing a companion).



    Parameters
    ----------
    array : 3D or 2D array 
        Input 3d cube or 2d image.
    bpix_map: 3D or 2D array, opt
        Input bad pixel array. Should have same dimenstions as array. If not
        provided, the algorithm will attempt to identify bad pixel clumps
        automatically.
    cy,cx : float or 1D array. opt
        Vector with approximate y and x coordinates of the star for each channel
        (cube_like), or single 2-elements vector (frame_like). Should be 
        provided if bpix_map is None and protect_psf set to True.
    fwhm: float or 1D array, opt
        Vector containing the full width half maximum of the PSF in pixels, for
        each channel (cube_like); or single value (frame_like). Shouod be 
        provided if bpix map is None.
    sig: float, optional
        Value representing the number of "sigmas" above or below the "median" of
        the neighbouring pixel, to consider a pixel as bad. See details on 
        parameter "m" of function reject_outlier.
    protect_psf: bool, {True, False}, optional
        True if you want to protect a circular region centered on the star 
        (1.8*fwhm radius) from any bpix corr. If False, there is a risk to 
        modify a psf peak value; but if True, real bpix within the core are 
        not corrected.
    verbose: bool, {False,True}, optional
        Whether to print the number of bad pixels and number of iterations 
        required for each frame.
    half_res_y: bool, {True,False}, optional
        Whether the input data has only half the angular resolution vertically 
        compared to horizontally (e.g. the case of SINFONI data); in other words
        there are always 2 rows of pixels with exactly the same values.
        The algorithm will just consider every other row (hence making it
        twice faster), then apply the bad pixel correction on all rows.
    min_thr: float or None, opt
        If provided, corresponds to a minimum absolute threshold below which
        pixels are not considered bad (can be used to avoid the identification
        of bad pixels within noise).
    max_nit: float, optional
        Maximum number of iterations on a frame to correct bpix. Typically, it 
        should be set to less than ny/2 or nx/2. This is a mean of precaution in
        case the algorithm gets stuck with 2 neighbouring pixels considered bpix
        alternately on two consecutively iterations hence leading to an infinite
        loop (very very rare case).
    full_output: bool, {False,True}, optional
        Whether to return as well the cube of bad pixel maps and the cube of 
        defined annuli.

    Returns:
    --------
    obj_tmp: 2d or 3d array; the bad pixel corrected frame/cube.
    If full_output is set to True, it returns as well:
    bpix_map: 2d or 3d array; the bad pixel map or the cube of bpix maps
    """

    obj_tmp = array.copy()
    ndims = obj_tmp.ndim
    assert ndims == 2 or ndims == 3, "Object is not two or three dimensional.\n"

    if bpm_mask is not None:
        if bpm_mask.shape[-2:] != array.shape[-2:]:
            raise TypeError("Bad pixel map has wrong y/x dimensions.")

    def bp_removal_2d(obj_tmp, cy, cx, fwhm, sig, protect_psf, min_thr, verbose):    
        n_x = obj_tmp.shape[1]
        n_y = obj_tmp.shape[0]

        if half_res_y:
            if n_y%2 != 0: 
                msg = 'The input frames do not have of an even number of rows. '
                msg2 = 'Hence, you should not use option half_res_y = True'
                raise ValueError(msg+msg2)
            n_y = int(n_y/2)
            frame = obj_tmp.copy()
            obj_tmp = np.zeros([n_y,n_x])
            for yy in range(n_y):
                obj_tmp[yy] = frame[2*yy]
            
        fwhm_round = int(round(fwhm))
        # This should reduce the chance to accidently correct a bright planet:
        if fwhm_round % 2 == 0:
            neighbor_box = max(3, fwhm_round+1) 
        else:
            neighbor_box = max(3, fwhm_round)
        nneig = sum(np.arange(3, neighbor_box+2, 2))

        
        #1/ Create a tuple-array with coordinates of a circle of radius 1.8*fwhm
        # centered on the approximate coordinates of the star
        if protect_psf:
            if half_res_y: 
                circl_new = ellipse(int(cy/2), cx, r_radius=0.9*fwhm, 
                                    c_radius=1.8*fwhm, shape=(n_y, n_x))
            else: circl_new = circle(cy, cx, radius=1.8*fwhm, 
                                     shape=(n_y, n_x))
        else: circl_new = []
    

        #3/ Create a bad pixel map, by detecting them with clip_array
        bp=clip_array(obj_tmp, sig, sig, out_good=False, neighbor=True,
                      num_neighbor=neighbor_box, mad=True)
        bpix_map = np.zeros_like(obj_tmp)  
        bpix_map[bp] = 1              
        nbpix_tot = np.sum(bpix_map)
        bpix_map[circl_new] = 0
        if min_thr is not None:
            bpix_map[np.where(np.abs(obj_tmp)<min_thr)] = 0
        nbpix_tbc = np.sum(bpix_map)
        bpix_map_cumul = np.zeros_like(bpix_map)
        bpix_map_cumul[:] = bpix_map[:]
        nit = 0

        #4/ Loop over the bpix correction with sigma_filter, until 0 bpix left
        while nbpix_tbc > 0 and nit < max_nit:
            nit = nit+1
            if verbose:
                print("Iteration {}: {} bpix in total, {} to be "
                      "corrected".format(nit, nbpix_tot, nbpix_tbc))
            obj_tmp = sigma_filter(obj_tmp, bpix_map, neighbor_box=neighbor_box,
                                   min_neighbors=nneig, verbose=verbose)
            bp=clip_array(obj_tmp, sig, sig, out_good=False, neighbor=True,
                          num_neighbor=neighbor_box, mad=True)
            bpix_map = np.zeros_like(obj_tmp)  
            bpix_map[bp] = 1
            nbpix_tot = np.sum(bpix_map)
            bpix_map[circl_new] = 0
            if min_thr is not None:
                bpix_map[np.where(np.abs(obj_tmp)<min_thr)] = 0
            nbpix_tbc = np.sum(bpix_map)
            bpix_map_cumul = bpix_map_cumul+bpix_map

        if verbose:
            print('All bad pixels are corrected.')
            
        if half_res_y:
            frame = obj_tmp.copy()
            frame_bpix = bpix_map_cumul.copy()
            n_y = 2*n_y
            obj_tmp = np.zeros([n_y,n_x])
            bpix_map_cumul = np.zeros([n_y,n_x])
            for yy in range(n_y):
                obj_tmp[yy] = frame[int(yy/2)]
                bpix_map_cumul[yy] = frame_bpix[int(yy/2)]

        return obj_tmp, bpix_map_cumul

    if ndims == 2:
        if bpm_mask is None:
            if (cy is None or cx is None) and protect_psf:
                cen = approx_stellar_position([obj_tmp], fwhm)
                cy = cen[0,0]
                cx = cen[0,1]
            obj_tmp, bpix_map_cumul = bp_removal_2d(obj_tmp, cy, cx, fwhm, sig, 
                                                    protect_psf, min_thr, 
                                                    verbose)
        else:
            fwhm_round = int(round(fwhm))
            fwhm_round = fwhm_round+1-(fwhm_round%2) # make it odd
            neighbor_box = max(3, fwhm_round) # to not replace a companion
            nneig = sum(np.arange(3, neighbor_box+2, 2))
            obj_tmp = sigma_filter(obj_tmp, bpm_mask, neighbor_box, nneig, 
                                   verbose)
            bpix_map_cumul = bpm_mask
                                            
    if ndims == 3:
        n_z = obj_tmp.shape[0]
        if bpm_mask is None:
            if cy is None or cx is None:
                cen = approx_stellar_position(obj_tmp, fwhm)
                cy = cen[:,0]
                cx = cen[:,1]
            elif isinstance(cy, (float,int)) and isinstance(cx, (float,int)): 
                cy = [cy]*n_z
                cx = [cx]*n_z
            if isinstance(fwhm, (float,int)):
                fwhm = [fwhm]*n_z
            bpix_map_cumul = np.zeros_like(obj_tmp)
            for i in range(n_z):
                if verbose: print('************Frame # ', i,' *************')
                obj_tmp[i], bpix_map_cumul[i] = bp_removal_2d(obj_tmp[i], cy[i], 
                                                              cx[i], fwhm[i], sig, 
                                                              protect_psf,  
                                                              min_thr, verbose)
        else:
            if isinstance(fwhm, (float,int)):
                fwhm_round = int(round(fwhm))
            else:
                fwhm_round = int(np.median(fwhm))
            fwhm_round = fwhm_round+1-(fwhm_round%2) # make it odd
            neighbor_box = max(3, fwhm_round) # to not replace a companion
            nneig = sum(np.arange(3, neighbor_box+2, 2))
            for i in range(n_z):
                if verbose: print('************Frame # ', i,' *************')
                if bpm_mask.ndim == 3:
                    bpm = bpm_mask[i]
                else:
                    bpm = bpm_mask
                obj_tmp[i] = sigma_filter(obj_tmp[i], bpm, neighbor_box, 
                                          nneig, verbose)
            bpix_map_cumul = bpm_mask
                                                 
    if full_output:
        return obj_tmp, bpix_map_cumul
    else:
        return obj_tmp
    
    
def find_outliers(frame, sig_dist, in_bpix=None, stddev=None, neighbor_box=3,
                  min_thr=None, mid_thr=None):
    """ Provides a bad pixel (or outlier) map for a given frame.

    Parameters
    ----------
    frame: 2d array 
        Input 2d image.
    sig_dist: float
        Threshold used to discriminate good from bad neighbours, in terms of 
        normalized distance to the median value of the set (see reject_outliers)
    in_bpix: 2d array, optional
        Input bpix map (typically known from the previous iteration), to only 
        look for bpix around those locations.
    neighbor_box: int, optional
        The side of the square window around each pixel where the sigma and 
        median are calculated for the bad pixel DETECTION and CORRECTION.
    min_thr: {None,float}, optional
        Any pixel whose value is lower than this threshold (expressed in adu)
        will be automatically considered bad and hence sigma_filtered. If None,
        it is not used.
    mid_thr: {None, float}, optional
        Pixels whose value is lower than this threshold (expressed in adu) will
        have its neighbours checked; if there is at max. 1 neighbour pixel whose
        value is lower than mid_thr+(5*stddev), then the pixel is considered bad
        (because it means it is a cold pixel in the middle of significant 
        signal). If None, it is not used.

    Returns
    -------
    bpix_map : numpy ndarray
        Output cube with frames indicating the location of bad pixels"""

    ndims = len(frame.shape)
    assert ndims == 2, "Object is not two dimensional.\n"

    nx = frame.shape[1]
    ny = frame.shape[0]
    bpix_map = np.zeros_like(frame)
    if stddev is None: stddev = np.std(frame)
    half_box = int(neighbor_box/2)
    
    if in_bpix is None:
        for xx in range(nx):
            for yy in range(ny):
                #0/ Determine the box of neighbouring pixels
                # half size of the box at the bottom of the pixel
                hbox_b = min(half_box, yy)        
                # half size of the box at the top of the pixel
                hbox_t = min(half_box, ny-1-yy)   
                # half size of the box to the left of the pixel
                hbox_l = min(half_box, xx)
                # half size of the box to the right of the pixel  
                hbox_r = min(half_box, nx-1-xx)    
                # but in case we are at an edge, we want to extend the box by 
                # one row/column of px in the direction opposite to the edge:
                if yy > ny-1-half_box:
                    hbox_b = hbox_b + (yy-(ny-1-half_box))
                elif yy < half_box:
                    hbox_t = hbox_t+(half_box-yy)
                if xx > nx-1-half_box:
                    hbox_l = hbox_l + (xx-(nx-1-half_box))
                elif xx < half_box:
                    hbox_r = hbox_r+(half_box-xx)

                #1/ list neighbouring pixels, >8 (NOT including pixel itself)
                neighbours = frame[yy-hbox_b:yy+hbox_t+1,
                                   xx-hbox_l:xx+hbox_r+1]
                idx_px = ([[hbox_b],[hbox_l]])
                flat_idx = np.ravel_multi_index(idx_px,(hbox_t+hbox_b+1,
                                                        hbox_r+hbox_l+1))
                neighbours = np.delete(neighbours,flat_idx)

                #2/ Det if central pixel is outlier
                test_result = reject_outliers(neighbours, frame[yy,xx], 
                                              m=sig_dist, stddev=stddev, 
                                              min_thr=min_thr, mid_thr=mid_thr)

                #3/ Assign the value of the test to bpix_map
                bpix_map[yy,xx] = test_result

    else:
        nb = int(np.sum(in_bpix))  # number of bad pixels at previous iteration
        wb = np.where(in_bpix)     # pixels to check
        bool_bpix= np.zeros_like(in_bpix)
        for n in range(nb):
            for yy in [max(0,wb[0][n]-half_box),wb[0][n],min(ny-1,wb[0][n]+half_box)]:
                for xx in [max(0,wb[1][n]-half_box),wb[1][n],min(ny-1,wb[1][n]+half_box)]:
                    bool_bpix[yy,xx] = 1
        nb = int(np.sum(bool_bpix))# true number of px to check  (including 
                                   # neighbours of bpix from previous iteration)
        wb = np.where(bool_bpix)   # true px to check
        for n in range(nb):
            #0/ Determine the box of neighbouring pixels
            # half size of the box at the bottom of the pixel
            hbox_b = min(half_box,wb[0][n])
            # half size of the box at the top of the pixel     
            hbox_t = min(half_box,ny-1-wb[0][n])
            # half size of the box to the left of the pixel
            hbox_l = min(half_box,wb[1][n])
            # half size of the box to the right of the pixel
            hbox_r = min(half_box,nx-1-wb[1][n])
            # but in case we are at an edge, we want to extend the box by one 
            # row/column of pixels in the direction opposite to the edge:
            if wb[0][n] > ny-1-half_box:
                hbox_b = hbox_b + (wb[0][n]-(ny-1-half_box))
            elif wb[0][n] < half_box:
                hbox_t = hbox_t+(half_box-wb[0][n])
            if wb[1][n] > nx-1-half_box:
                hbox_l = hbox_l + (wb[1][n]-(nx-1-half_box))
            elif wb[1][n] < half_box:
                hbox_r = hbox_r+(half_box-wb[1][n])

            #1/ list neighbouring pixels, > 8, not including the pixel itself
            neighbours = frame[wb[0][n]-hbox_b:wb[0][n]+hbox_t+1,
                               wb[1][n]-hbox_l:wb[1][n]+hbox_r+1]
            c_idx_px = ([[hbox_b],[hbox_l]])
            flat_c_idx = np.ravel_multi_index(c_idx_px,(hbox_t+hbox_b+1,
                                                        hbox_r+hbox_l+1))
            neighbours = np.delete(neighbours,flat_c_idx)

            #2/ test if bpix
            test_result = reject_outliers(neighbours, frame[wb[0][n],wb[1][n]],
                                          m=sig_dist, stddev=stddev, 
                                          min_thr=min_thr, mid_thr=mid_thr)

            #3/ Assign the value of the test to bpix_map
            bpix_map[wb[0][n],wb[1][n]] = test_result


    return bpix_map
    
    

def reject_outliers(data, test_value, m=5., stddev=None, debug=False):
    """ Function to reject outliers from a set.
    Instead of the classic standard deviation criterion (e.g. 5-sigma), the 
    discriminant is determined as follow:
    - for each value in data, an absolute distance to the median of data is
    computed and put in a new array "d" (of same size as data)
    - scaling each element of "d" by the median value of "d" gives the absolute
    distances "s" of each element
    - each "s" is then compared to "m" (parameter): if s < m, we have a good 
    neighbour, otherwise we have an outlier. A specific value test_value is 
    tested as outlier.

    Parameters:
    -----------
    data: numpy ndarray
        Input array with respect to which either a test_value or the central a 
        value of data is determined to be an outlier or not
    test_value: float
        Value to be tested as an outlier in the context of the input array data
    m: float, optional
        Criterion used to test if test_value is or pixels of data are outlier(s)
        (similar to the number of "sigma" in std_dev statistics)
    stddev: float, optional (but strongly recommended)
        Global std dev of the non-PSF part of the considered frame. It is needed
        as a reference to know the typical variation of the noise, and hence 
        avoid detecting outliers out of very close pixel values. If the 9 pixels
        of data happen to be very uniform in values at some location, the 
        departure in value of only one pixel could make it appear as a bad 
        pixel. If stddev is not provided, the stddev of data is used (not 
        recommended).

    Returns:
    --------
    test_result: 0 or 1
        0 if test_value is not an outlier. 1 otherwise. 
    """

    if no_numba:
        def _reject_outliers(data, test_value, m=5., stddev=None, debug=False):
            if stddev is None:
                stddev = np.std(data)
        
            med = np.median(data)
            d = np.abs(data - med)
            mdev = np.median(d)
            if debug:
                print("data = ", data)
                print("median(data)= ", np.median(data))
                print("d = ", d)
                print("mdev = ", mdev)
                print("stddev(box) = ", np.std(data))
                print("stddev(frame) = ", stddev)
                print("max(d) = ", np.max(d))
        
            if max(np.max(d),np.abs(test_value-med)) > stddev:
                mdev = mdev if mdev>stddev else stddev
                s = d/mdev
                if debug:
                    print("s =", s)
                test = np.abs((test_value-np.median(data))/mdev)
                if debug:
                    print("test =", test)
                else:
                    if test < m:
                        test_result = 0
                    else:
                        test_result = 1
            else:
                test_result = 0
        
            return test_result
        return _reject_outliers(data, test_value, m=5., stddev=None, 
                                debug=debug)
    else:
        @njit
        def _reject_outliers(data, test_value, m=5.,stddev=None):
            if stddev is None:
                stddev = np.std(data)
        
            med = np.median(data)
            d = data.copy()
            d_flat = d.flatten()
            for i in range(d_flat.shape[0]):
                d_flat[i] = np.abs(data.flatten()[i] - med)
            mdev = np.median(d_flat)
            if max(np.max(d),np.abs(test_value-med)) > stddev:
                test = np.abs((test_value-med)/mdev)
                if test < m:
                    test_result = 0
                else:
                    test_result = 1
            else:
                test_result = 0
            
            return test_result
        
        return _reject_outliers(data, test_value, m=5.,stddev=None)

  
def correct_ann_outliers(obj_tmp, ann_width, sig, med_neig, std_neig, cy, cx, 
                          min_thr, max_thr, rand_arr, stddev, half_res_y=False):
    """ Function to correct outliers in concentric annuli.

    Parameters:
    -----------
    obj_tmp: numpy ndarray
        Input array with respect to which either a test_value or the central a 
        value of data is determined to be an outlier or not
    ann_width: float
        Width of concenrtric annuli in pixels.
    sig: float
        Number of sigma to consider a pixel intensity as an outlier.
    med_neig, std_neig: 1d arrays
        Median and standard deviation of good pixel intensities in each annulus 
    cy, cx: floats
        Coordinates of the center of the concentric annuli.
    min_thr, max_thr: {None,float}
        Any pixel whose value is lower (resp. larger) than this threshold will 
        be automatically considered bad and hence sigma_filtered. If None, it 
        is not used.
    stddev: float
        Global std dev of the non-PSF part of the considered frame. It is needed
        as a reference to know the typical variation of the noise, and hence 
        avoid detecting outliers out of very close pixel values. If the 9 pixels
        of data happen to be very uniform in values at some location, the 
        departure in value of only one pixel could make it appear as a bad 
        pixel. If stddev is not provided, the stddev of data is used (not 
        recommended).
    half_res_y: bool, {True,False}, optional
        Whether the input data have only half the angular resolution vertically 
        compared to horizontally (e.g. SINFONI data).
        The algorithm will then correct the bad pixels every other row.

    Returns:
    --------
    obj_tmp_corr: np.array
        Array with corrected outliers.
    bpix_map: np.array
        Boolean array with location of outliers.
    """ 
    
    if no_numba: 
        def _correct_ann_outliers(obj_tmp, ann_width, sig, med_neig, std_neig, 
                                  cy, cx, min_thr, max_thr, rand_arr, stddev, 
                                  half_res_y=False):           
            n_y, n_x = obj_tmp.shape
            rand_arr = 2*(np.random.rand((n_y, n_x))-0.5)
            obj_tmp_corr = obj_tmp.copy()
            bpix_map = np.zeros([n_y,n_x])
            for yy in range(n_y):
                for xx in range(n_x):
                    if half_res_y:
                        rad = np.sqrt((2*(cy-yy))**2+(cx-xx)**2)
                    else:
                        rad = np.sqrt((cy-yy)**2+(cx-xx)**2)
                    rr = int(rad/ann_width)
                    dev = max(stddev,min(std_neig[rr],med_neig[rr]))
        
                    # check min_thr
                    if obj_tmp[yy,xx] < min_thr:
                        bpix_map[yy,xx] = 1
                        obj_tmp_corr[yy,xx] = med_neig[rr] + \
                                              np.sqrt(np.abs(med_neig[rr]))*rand_arr[yy,xx]
        
                    # check max_thr
                    elif obj_tmp[yy,xx] > max_thr:
                        bpix_map[yy,xx] = 1
                        obj_tmp_corr[yy,xx] = med_neig[rr] + \
                                              np.sqrt(np.abs(med_neig[rr]))*rand_arr[yy,xx]
                                              
                    elif (obj_tmp[yy,xx] < med_neig[rr]-sig*dev or 
                          obj_tmp[yy,xx] > med_neig[rr]+sig*dev):
                        bpix_map[yy,xx] = 1
                        obj_tmp_corr[yy,xx] = med_neig[rr] + \
                                              np.sqrt(np.abs(med_neig[rr]))*rand_arr[yy,xx]
            return obj_tmp_corr, bpix_map
    else:
        @njit  
        def _correct_ann_outliers(obj_tmp, ann_width, sig, med_neig, std_neig, 
                                  cy, cx, min_thr, max_thr, rand_arr, stddev, 
                                  half_res_y=False):           
            n_y, n_x = obj_tmp.shape
            rand_arr = 2*(np.random.rand((n_y, n_x))-0.5)
            obj_tmp_corr = obj_tmp.copy()
            bpix_map = np.zeros([n_y,n_x])
            for yy in range(n_y):
                for xx in range(n_x):
                    if half_res_y:
                        rad = np.sqrt((2*(cy-yy))**2+(cx-xx)**2)
                    else:
                        rad = np.sqrt((cy-yy)**2+(cx-xx)**2)
                    rr = int(rad/ann_width)
                    dev = max(stddev,min(std_neig[rr],med_neig[rr]))
        
                    # check min_thr
                    if obj_tmp[yy,xx] < min_thr:
                        bpix_map[yy,xx] = 1
                        obj_tmp_corr[yy,xx] = med_neig[rr] + \
                                              np.sqrt(np.abs(med_neig[rr]))*rand_arr[yy,xx]
        
                    # check max_thr
                    elif obj_tmp[yy,xx] > max_thr:
                        bpix_map[yy,xx] = 1
                        obj_tmp_corr[yy,xx] = med_neig[rr] + \
                                              np.sqrt(np.abs(med_neig[rr]))*rand_arr[yy,xx]
                                              
                    elif (obj_tmp[yy,xx] < med_neig[rr]-sig*dev or 
                          obj_tmp[yy,xx] > med_neig[rr]+sig*dev):
                        bpix_map[yy,xx] = 1
                        obj_tmp_corr[yy,xx] = med_neig[rr] + \
                                              np.sqrt(np.abs(med_neig[rr]))*rand_arr[yy,xx]
            return obj_tmp_corr, bpix_map
    
    return _correct_ann_outliers(obj_tmp, ann_width, sig, med_neig, std_neig, 
                                 cy, cx, min_thr, max_thr, rand_arr, stddev, 
                                 half_res_y=False)