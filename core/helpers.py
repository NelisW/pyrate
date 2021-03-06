#!/usr/bin/env/python
"""
Pyrate - Optical raytracing based on Python

Copyright (C) 2014 Moritz Esslinger moritz.esslinger@web.de
               and Johannes Hartung j.hartung@gmx.net
               and    Uwe Lippmann  uwe.lippmann@web.de

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

"""
Here are global convenience and helper functions located.
"""

import numpy as np

from optical_system import OpticalSystem
import localcoordinates
from optical_element import OpticalElement
from surface import Surface
from surfShape import Conic
from globalconstants import numerical_tolerance, canonical_ey, standard_wavelength
from ray import RayBundle
from material_isotropic import ConstantIndexGlass
from helpers_math import rodrigues
from material_glasscat import refractiveindex_dot_info_glasscatalog

import logging


def build_simple_optical_system(builduplist, material_db_path = ""):

    """
    Convenience function to build up an centrosymmetric system with spherical lenses.

    :param builduplist: (list of tuple)
             elements are (r, cc, thickness, mat, comment)
             r - radius of curvature (float)
             cc - conic constant (float)
             thickness - (float)
             mat - material index or name (str)
                   if convertable to float, a ConstantIndexGlass will be created
                   if not, a material from the refractiveindex.info will be created

    :param material_db_path: (str)
             path to the refractiveindex.info yml-database

    :return (s, stdseq): (tuple)
             s is an OpticalSystem object
             stdseq is a sequence for sequential raytracing
    """
    logger = logging.getLogger(__name__)    
    
    logger.info("Creating optical system")    
    s = OpticalSystem() 
    
    
    lc0 = s.addLocalCoordinateSystem(localcoordinates.LocalCoordinates(name="object", decz=0.0), refname=s.rootcoordinatesystem.name)

    elem = OpticalElement(lc0, name="stdelem")
        
    refname = lc0.name
    lastmat = None
    surflist_for_sequence = []

    gcat = refractiveindex_dot_info_glasscatalog( material_db_path )

    for (r, cc, thickness, mat, comment) in builduplist:
        
        lc = s.addLocalCoordinateSystem(localcoordinates.LocalCoordinates(name=comment, decz=thickness), refname=refname)
        curv = 0
        if abs(r) > numerical_tolerance:
            curv = 1./r
        else:
            curv = 0.
        actsurf = Surface(lc, shape=Conic(lc, curv=curv, cc=cc))

        if mat is not None:
            try:
                n = float(mat)
            except:
                gcat.getMaterialDictFromLongName( mat )
                
                elem.addMaterial(mat, gcat.createGlassObjectFromLongName(lc, mat) )
            else:
                elem.addMaterial(mat, ConstantIndexGlass(lc, n=n))

        elem.addSurface(comment, actsurf, (lastmat, mat))
        logger.info("Added surface: %s at material boundary %s" % (comment, (lastmat, mat)))        
        
        lastmat = mat
        refname = lc.name
        surflist_for_sequence.append((comment, {}))
            
    s.addElement("stdelem", elem)
    stdseq = [("stdelem", surflist_for_sequence)]    

    return (s, stdseq)



# two coordinate systems for build_pilotbundle
# one x, one k
# kpilot given as unity vector times 2pi/lambda relative to second coordinate system
# if none given than k = kz
# k = kcomp unity in determinant => solution => poynting vector
# scalarproduct poynting vector * k > 0
# give pilot a polarization lives in k coordinate system
# <Re k, S> > 0 and <Im k, S> > 0


def choose_nearest(kvec, kvecs_new):
    """
    Choose kvec from solution vector which is nearest to a specified kvec.
    
    param kvec: specified k-vector (3xN numpy array of complex) which is used as reference.
    param kvecs_new: (4x3xN numpy array of complex) solution arrays of kvectors.
    
    return: vector from kvecs_new which is nearest to kvec.
    """
    
    tol = 1e-3
    (kvec_dim, kvec_len) = np.shape(kvec)
    (kvec_new_no, kvec_new_dim, kvec_new_len) = np.shape(kvecs_new)
    
    res = np.zeros_like(kvec)    
    
    if kvec_new_dim == kvec_dim and kvec_len == kvec_new_len:
        for j in range(kvec_len):
            diff_comparison = 1e10
            choosing_index = 0
            for i in range(kvec_new_no):
                vdiff = kvecs_new[i, :, j] - kvec[:, j]
                hermite_abs_square = np.dot(np.conj(vdiff), vdiff)
                if  hermite_abs_square < diff_comparison and hermite_abs_square > tol:
                    choosing_index = i
                    diff_comparison = hermite_abs_square
            res[:, j] = kvecs_new[choosing_index, :, j]
    return res

    


def collimated_bundle(nrays, startz, starty, radius, rast):
    # FIXME: this function does not respect the dispersion relation in the material

    rstobj = rast
    (px, py) = rstobj.getGrid(nrays)
    rpup = radius
    o = np.vstack((rpup*px, rpup*py + starty, startz*np.ones_like(px)))
    k = np.zeros_like(o)
    k[2,:] = 1. #2.*math.pi/wavelength
    E0 = np.cross(k, canonical_ey, axisa=0, axisb=0).T
    return (o, k, E0)


def build_pilotbundle(surfobj, mat, (dx, dy), (phix, phiy), Elock=None, 
                      kunitvector=None, lck=None, wave=standard_wavelength, 
                      num_sampling_points=5, random_xy=False):

    """
    Simplified pilotbundle generation.
    
    param surfobj: (Surface object) denotes the object surface, where to start
                        the raytracing
    param mat: (Material object) denotes the background material in which the
                pilotbundle starts
    param (dx, dy): (float) infinitesimal distances of pilotbundles in plane of
                object surface
    param (dphix, dphiy): (float) infinitesimal angles for angular cones at
                pilotbundle start points at object surface
    param Elock: (3xN numpy array of complex) E field vector in local k coordinate system
    param kunitvector: (3xN numpy array of float) unit vector of k vector which is
                used to generate the cones around
    param lck: (LocalCoordinates object) local k coordinate system if it differs from
                local object coordinate system
    param wavelength: (float) wavelength of the pilotbundle
    param num_sampling_points: (int) number of sampling points in every direction
    param random_xy: (bool) choose xy distribution randomly?
    
    """
    
    # TODO: remove code doubling from material due to sorting of K and E
    # TODO: check K and E from unit vector (fulfill ev equation?)
    # TODO: check why there are singular matrices generated in calculateXYUV

    def generate_cone_xy_bilinear(
        direction_vec, lim_angle, 
        (centerx, centery), (dx, dy), 
        num_pts_dir, random_xy=False):

        if not random_xy:
            num_pts_lspace = num_pts_dir
            if num_pts_dir % 2 == 1:
                num_pts_lspace -= 1
    
            lspace = np.hstack(
                (np.linspace(-1, 0, num_pts_lspace/2, endpoint=False), 
                 np.linspace(1, 0, num_pts_lspace/2, endpoint=False)
                 )
                 )
            
            lspace = np.hstack((0, lspace))

            x = centerx + dx*lspace
            y = centery + dy*lspace
        else:
            x = centerx + dx*np.hstack((0, 1.-2.*np.random.random(num_pts_dir-1)))
            y = centery + dy*np.hstack((0, 1.-2.*np.random.random(num_pts_dir-1)))
        
        phi = np.arctan2(direction_vec[1], direction_vec[0])
        theta = np.arcsin(np.sqrt(direction_vec[1]**2 + direction_vec[0]**2))

        alpha = np.linspace(-lim_angle, 0, num_pts_dir, endpoint=False)
        angle = np.linspace(0, 2.*np.pi, num_pts_dir, endpoint=False)
        
        (Alpha, Angle, X, Y) = np.meshgrid(alpha, angle, x, y)
        Xc = np.cos(Angle)*np.sin(Alpha)
        Yc = np.sin(Angle)*np.sin(Alpha)
        Zc = np.cos(Alpha)        
        
        start_pts = np.vstack((X.flatten(), Y.flatten(), np.zeros_like(X.flatten())))

        cone = np.vstack((Xc.flatten(), Yc.flatten(), Zc.flatten()))

        rotz = rodrigues(-phi, [0, 0, 1])
        rottheta = rodrigues(-theta, [1, 0, 0])

        finalrot = np.dot(rottheta, rotz)

        final_cone = np.dot(finalrot, cone)

        return (start_pts, final_cone)        



    lcobj = surfobj.rootcoordinatesystem
    if lck is None:
        lck = lcobj
    if kunitvector is None:
        # standard direction is in z in lck
        kunitvector = np.array([0, 0, 1])
        
    cone_angle = 0.5*(phix + phiy)     
    (xlocobj, kconek) = generate_cone_xy_bilinear(kunitvector, cone_angle, (0.0, 0.0), (dx, dy), num_sampling_points, random_xy=random_xy)

    xlocmat = mat.lc.returnOtherToActualPoints(xlocobj, lcobj)
    kconemat = mat.lc.returnOtherToActualDirections(kconek, lck)
    xlocsurf = surfobj.shape.lc.returnOtherToActualPoints(xlocobj, lcobj)    
    surfnormalmat = mat.lc.returnOtherToActualDirections(surfobj.shape.getNormal(xlocsurf[0], xlocsurf[1]), surfobj.shape.lc)    
    
    (k_4, E_4) = mat.sortKnormUnitEField(xlocmat, kconemat, surfnormalmat, wave=wave)
    
    
    pilotbundles =[]
    for j in range(4):
       
        xglob = lcobj.returnLocalToGlobalPoints(xlocobj)
        kglob = mat.lc.returnLocalToGlobalDirections(k_4[j])
        Eglob = mat.lc.returnLocalToGlobalDirections(E_4[j])
                
        pilotbundles.append(RayBundle(
                x0 = xglob, 
                k0 = kglob, 
                Efield0 = Eglob, wave=wave
                ))
    return pilotbundles