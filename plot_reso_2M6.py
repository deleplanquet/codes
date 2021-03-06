import numpy as np
import pickle
from pylab import *
import math
import cmath
import matplotlib.pyplot as plt
import os
import sys
from scipy import interpolate
from scipy.signal import hilbert
from obspy import read
from obspy.signal.util import smooth
from scipy import ndimage
from obspy import Trace
#from mpl_toolkits.basemap import Basemap

#fonctions

#conversion angle degre -> radian
def d2r(angle):
    return angle*math.pi/180

#conversion angle radian -> degre
def r2d(angle):
    return angle*180/math.pi

#conversion coordonnees geographiques -> cartesien
def geo2cart(r, lat, lon):
    rlat = d2r(lat)
    rlon = d2r(lon)
    xx = r*math.cos(rlat)*math.cos(rlon)
    yy = r*math.cos(rlat)*math.sin(rlon)
    zz = r*math.sin(rlat)
    return [xx, yy, zz]

#normalisation
def norm(vect):
    Norm = math.sqrt(vect[0]*vect[0] + vect[1]*vect[1] + vect[2]*vect[2])
    return [vect[0]/Norm, vect[1]/Norm, vect[2]/Norm]

#rotation 3d d'angle theta et d'axe passant par l'origine porte par le vecteur (a, b, c) de norme 1, repere orthonormal direct
def rotation(u, theta, OM):
    """ attention OM unitaire """
    a = norm(OM)[0]
    b = norm(OM)[1]
    c = norm(OM)[2]
    radian = d2r(theta)
    #coefficients de la matrice de rotation
    mat = array([[a*a + (1 - a*a)*math.cos(radian),
                  a*b*(1 - math.cos(radian)) - c*math.sin(radian),
                  a*c*(1 - math.cos(radian)) + b*math.sin(radian)],
                 [a*b*(1 - math.cos(radian)) + c*math.sin(radian),
                  b*b + (1 - b*b)*math.cos(radian),
                  b*c*(1 - math.cos(radian)) - a*math.sin(radian)],
                 [a*c*(1 - math.cos(radian)) - b*math.sin(radian),
                  b*c*(1 - math.cos(radian)) + a*math.sin(radian),
                  c*c + (1 - c*c)*math.cos(radian)]])
    #rearrangement du vecteur auquel on applique la rotation
    vect = array([[u[0]],
                  [u[1]],
                  [u[2]]])
    #rotation du vecteur u de theta autour de OM
    vect_rot = dot(mat, vect)
    return (vect_rot[0][0], vect_rot[1][0], vect_rot[2][0])

#bissectrice en 3d
def milieu(lat1, long1, lat2, long2):
    x1, y1, z1 = geo2cart(1, lat1, long1)
    x2, y2, z2 = geo2cart(1, lat2, long2)
    x_m = x1 + x2
    y_m = y1 + y2
    z_m = z1 + z2
    return [r2d(math.asin(z_m/math.sqrt(x_m*x_m + y_m*y_m + z_m*z_m))),
            r2d(math.acos(x_m/math.sqrt(x_m*x_m + y_m*y_m)))]

#calcul de la matrice des tps de trajet pour une station
def fault(cen_fault, length, width, u_strike, u_dip, pasx, pasy):
    x_cf, y_cf, z_cf = geo2cart(cen_fault[0], cen_fault[1], cen_fault[2])
    x_fault = np.arange(-length/2/pasx, length/2/pasx)
    #y_fault = np.arange(0, width/pasy)
    y_fault = np.arange(-width/2/pasy, width/2/pasy)
    grill_fault = np.zeros((len(x_fault), len(y_fault), 3))
    for a in x_fault:
        for b in y_fault:
            grill_fault[np.where(x_fault==a), np.where(y_fault==b), 0] = x_cf + a*pasx*u_strike[0] + b*pasy*u_dip[0]
            grill_fault[np.where(x_fault==a), np.where(y_fault==b), 1] = y_cf + a*pasx*u_strike[1] + b*pasy*u_dip[1]
            grill_fault[np.where(x_fault==a), np.where(y_fault==b), 2] = z_cf + a*pasx*u_strike[2] + b*pasy*u_dip[2]
    return grill_fault

#calcul de la matrice des tps de trajet pour une station
def trav_time(station, fault, velocity):
    x_sta, y_sta, z_sta = geo2cart(R_Earth + station[0]/1000, station[1], station[2])
    mat_time = np.zeros((len(fault[:, 0, 0]), len(fault[0, :, 0])))
    for a in range(len(fault[:, 0, 0])):
        for b in range(len(fault[0, :, 0])):
            mat_time[a, b] = math.sqrt(pow(x_sta - fault[a, b, 0], 2)
                                        + pow(y_sta - fault[a, b, 1], 2)
                                        + pow(z_sta - fault[a, b, 2], 2))/velocity
    return mat_time

#distance entre deux points, coordonnees cartesiennes
def dist(la1, lo1, el1, la2, lo2, el2):
    x1, y1, z1 = geo2cart(R_Earth + el1, la1, lo1)
    x2, y2, z2 = geo2cart(R_Earth + el2, la2, lo2)
    return pow(pow(x1 - x2, 2) + pow(y1 - y2, 2) + pow(z1 - z2, 2), 0.5)

#normalisation avec max = 1
def norm1(vect):
    return [10*a/vect.max() for a in vect]

#fonction gaussienne
def gauss(x_data, H, mu):
    sigma = H/2.3548
    y_data = np.zeros(len(x_data))
    for i in range(len(x_data)):
        y_data[i] = 1./(sigma*math.sqrt(2))*math.exp(-(x_data[i] - mu)*(x_data[i] - mu)/(2*sigma*sigma))
    return y_data

#calcul distance et azimuth d'un point par rapport a un autre
''' distance et azimuth de B par rapport a A -> dist_azim(A, B) '''
def dist_azim(ptA, ptB):
    latA = d2r(ptA[0])
    lonA = d2r(ptA[1])
    latB = d2r(ptB[0])
    lonB = d2r(ptB[1])
    dist_rad = math.acos(math.sin(latA)*math.sin(latB) + math.cos(latA)*math.cos(latB)*math.cos(lonB - lonA))
    angle_brut = math.acos((math.sin(latB) - math.sin(latA)*math.cos(dist_rad))/(math.cos(latA)*math.sin(dist_rad)))
    if math.sin(lonB - lonA) > 0:
        return R_Earth*dist_rad, r2d(angle_brut)
    else:
        return R_Earth*dist_rad, 360 - r2d(angle_brut)

path_origin = os.getcwd()[:-6]
os.chdir(path_origin + '/Kumamoto')
with open('parametres_bin', 'rb') as my_fch:
    my_dpck = pickle.Unpickler(my_fch)
    param = my_dpck.load()

dossier = param['dossier']
dt_type = param['composante']
hyp_bp = param['ondes_select']
couronne = param['couronne']
frq = param['band_freq']
azim = param['angle']

path = path_origin + '/Kumamoto/' + dossier
path_data = path + '/' + dossier + '_vel_' + couronne + 'km_' + frq + 'Hz/' + dossier + '_vel_' + couronne + 'km_' + frq + 'Hz_' + dt_type + '_env_smooth_' + hyp_bp + '_' + azim + 'deg'
#path_data = path + '/' + dossier + '_results/' + dossier + '_vel_' + couronne + 'km_' + frq + 'Hz'
path_results = path + '/' + dossier + '_results/' + dossier + '_vel_' + couronne + 'km_' + frq + 'Hz/2M6'

if os.path.isdir(path_results) == False:
    os.makedirs(path_results)

lst_fch = []

lst_fch = os.listdir(path_data)




#recuperation position stations
print('     recuperation position stations')

dossier_seisme = sys.argv[1]
dt_type = sys.argv[2]
select_station = sys.argv[3]
couronne = '50-80km'

#dossier_seisme = dossier_seisme[0:-1]
print('     ', dossier_seisme, dt_type, select_station)

path_origin = os.getcwd()[:-6]
path = path_origin + '/Kumamoto/' + dossier_seisme

#lst_frq = ['02_05', '05_1', '1_2', '2_4', '4_8', '8_16', '16_30']
lst_frq = ['1_2', '2_4', '4_8', '8_16', '16_30']
lst_pth_dt = []

for freq in lst_frq:
    pth_dt = path + '/' + dossier_seisme + '_vel_' + couronne + '_' + freq + 'Hz/' + dossier_seisme + '_vel_' + couronne + '_' + freq + 'Hz'
    #lst_pth_dt.append(pth_dt + '_' + dt_type + '_env_smooth_' + select_station + '_impulse')
    lst_pth_dt.append(pth_dt + '_' + dt_type + '_env_smooth_' + select_station)

path_results = path + '/' + dossier_seisme + '_results'
#lst_rslt_2 = []

#for freq in lst_frq:
#    lst_rslt_2.append(path_results + '/' + dossier_seisme + '_vel_0-50km_' + freq + 'Hz_' + dt_type + '_env_smooth_' + select_station + '_2D_n=2/Traces')
#    if os.path.isdir(lst_rslt_2[lst_frq.index(freq)]) == False:
#        os.makedirs(lst_rslt_2[lst_frq.index(freq)])

if os.path.isdir(path_results) == False:
    os.makedirs(path_results)

lst_pth_fch = []

for freq in lst_frq:
    lst_pth_fch.append(os.listdir(lst_pth_dt[lst_frq.index(freq)]))

os.chdir(path)
with open(dossier_seisme + '_veldata', 'rb') as mon_fich:
    mon_depick = pickle.Unpickler(mon_fich)
    dict_vel = mon_depick.load()

os.chdir(path_origin + '/Kumamoto')
with open('ref_seismes_bin', 'rb') as my_fch:
    my_dpck = pickle.Unpickler(my_fch)
    dict_seis = my_dpck.load()

#constantes
R_Earth = 6400
v_P = 5.8
v_S = 3.4

vel_used = v_S
dict_vel_used = dict_vel[1]

dict_delai = dict_vel[2]

print(vel_used)
print('vP', v_P, 'vS',  v_S)

#recuperation position faille
strike = 224
dip = 65
l_fault = 100
w_fault = 40
lat_fault = [32.6477, 32.9858]
long_fault = [130.7071, 131.1216]
pas_l = 2
pas_w = 2

#placement de la faille
print('     localisation de la faille en volume')

lat_cen_fault, long_cen_fault = milieu(lat_fault[0], long_fault[0], lat_fault[1], long_fault[1])
dir_cen_fault = [math.cos(d2r(lat_cen_fault))*math.cos(d2r(long_cen_fault)), math.cos(d2r(lat_cen_fault))*math.sin(d2r(long_cen_fault)), math.sin(d2r(lat_cen_fault))]
vect_nord = rotation(dir_cen_fault, 90, [math.sin(d2r(long_cen_fault)), -math.cos(d2r(long_cen_fault)), 0])
vect_strike = rotation(vect_nord, -strike, dir_cen_fault)
vect_perp_strike = rotation(vect_nord, -strike-90, dir_cen_fault)
vect_dip = rotation(vect_perp_strike, dip, vect_strike)

#coord_fault = fault([6400, lat_cen_fault, long_cen_fault], l_fault, w_fault, norm(vect_strike), norm(vect_dip), pas_l, pas_w)
coord_fault = fault([6400 - dict_seis[dossier_seisme]['dep'], dict_seis[dossier_seisme]['lat'], dict_seis[dossier_seisme]['lon']], l_fault, w_fault, norm(vect_strike), norm(vect_dip), pas_l, pas_w)

#stacks
print('     stacks envelop')

samp_rate = 10 # st[0].stats.sampling_rate = 100
length_t = int(20*samp_rate)

tstart_ref = None
        
os.chdir(lst_pth_dt[4])
for fichier in lst_pth_fch[4]:
    st = read(fichier)
    if tstart_ref == None or tstart_ref > dict_delai[st[0].stats.station]:
        tstart_ref = dict_delai[st[0].stats.station]

for freq in lst_frq:
    os.chdir(lst_pth_dt[lst_frq.index(freq)])

    travt = []
    tmin = None
    dmin = None
    for fichier in lst_pth_fch[lst_frq.index(freq)]:
        st = read(fichier)
        travt.append(trav_time([st[0].stats.sac.stel, st[0].stats.sac.stla, st[0].stats.sac.stlo], coord_fault, vel_used))
        if dmin == None or dmin > st[0].stats.sac.dist:
            dmin = st[0].stats.sac.dist
        if tmin == None or tmin > st[0].stats.sac.t0:
            tmin = st[0].stats.sac.t0
    print(tmin)

    stack = np.zeros((int(l_fault/pas_l), int(w_fault/pas_w), length_t))

    for station in lst_pth_fch[lst_frq.index(freq)]:
        os.chdir(lst_pth_dt[lst_frq.index(freq)])
        st = read(station)
        tstart = st[0].stats.starttime
        env_norm = norm1(st[0].data)
        t = np.arange(st[0].stats.npts)/st[0].stats.sampling_rate
        f = interpolate.interp1d(t, env_norm)

        ista = lst_pth_fch[lst_frq.index(freq)].index(station)
        print('     ', station, st[0].stats.sampling_rate, str(ista + 1), '/', len(lst_pth_fch[lst_frq.index(freq)]))

        for ix in range(int(l_fault/pas_l)):
    	    for iy in range(int(w_fault/pas_w)):
    	    	for it in range(length_t):
                    #tshift = travt[ista][ix, iy] + dict_vel_used[st[0].stats.station] - 15 + it/samp_rate
                    #tshift = travt[ista][ix, iy] - dmin/v_S + tmin - 5 + it/samp_rate
                    tshift = tstart_ref - dict_delai[st[0].stats.station] + travt[ista][ix, iy] - dmin/v_S + tmin - 5 + dict_vel_used[st[0].stats.station] + it/samp_rate
                    if ix == 0 and iy == 0 and it == 0:
                        st[0].stats.sac.user1 = 0
                        st[0].stats.sac.user2 = 0
                        st[0].stats.sac.user3 = 0
                    if tshift > 0 and tshift < t[-1]:
                        if ix > 1:
                            stack[ix-2, iy, it] = stack[ix-2, iy, it] + 1./len(lst_pth_fch[lst_frq.index(freq)])*f(tshift)
                        if ix < 48 and it < 173:
                            stack[ix+2, iy, it+27] = stack[ix+2, iy, it+27] + 1./len(lst_pth_fch[lst_frq.index(freq)])*f(tshift)
                        #if ix == 24 and iy == 9 and it == 60:
                        #    st[0].stats.sac.user1 = tshift
                        #if ix == 26 and iy == 9 and it == 80:
                        #    st[0].stats.sac.user2 = tshift
                        #if ix == 22 and iy == 9 and it == 97:
                        #    st[0].stats.sac.user3 = tshift

        #tr = Trace(st[0].data, st[0].stats)
        #os.chdir(lst_rslt_2[lst_frq.index(freq)])
        #tr.write(station, format = 'SAC')

    os.chdir(path_results)
    with open(dossier_seisme + '_vel_' + couronne + '_' + freq + 'Hz_' + dt_type + '_env_smooth_' + select_station + '_stack2D_2M6_8km', 'wb') as my_fch:
    	my_pck = pickle.Pickler(my_fch)
    	my_pck.dump(stack)
