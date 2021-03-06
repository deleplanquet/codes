# make a copie of the records in SAC format of the stations which hypocenter
# distance is less than 100 km

import pickle
from obspy import read
import sys
import os
import math
from obspy import Trace

# few functions used in this script
# a library may be done

# conversion angle degree -> radian
def d2r(angle):
    return angle*math.pi/180

# conversion angle radian -> degree
def r2d(angle):
    return angle*180/math.pi

# conversion geographic coordinates -> cartesian coordinates
# outputs xx, yy and zz have same units than r and should be kilometer
def geo2cart(vect):
    r = vect[0]
    rlat = d2r(vect[1])
    rlon = d2r(vect[2])
    xx = r*math.cos(rlat)*math.cos(rlon)
    yy = r*math.cos(rlat)*math.sin(rlon)
    zz = r*math.sin(rlat)
    return [xx, yy, zz]

# distance between two points whose coordinates are cartesians
def dist(vect1, vect2):
    x1, y1, z1 = geo2cart(vect1)
    x2, y2, z2 = geo2cart(vect2)
    return pow(pow(x1 - x2, 2) + pow(y1 - y2, 2) + pow(z1 - z2, 2), 0.5)

# azimuth between two points
# the reference point is the first given and the azimuth of the second point is
# calculated with respect to the first one
def azim(ptA, ptB):
    latA, lonA = (d2r(ptA[1]), d2r(ptA[2]))
    latB, lonB = (d2r(ptB[1]), d2r(ptB[2]))
    dst_rad = math.acos(math.sin(latA)*math.sin(latB)
                        + math.cos(latA)*math.cos(latB)*math.cos(lonB - lonA))
    azm_rad = math.acos((math.sin(latB) - math.sin(latA)*math.cos(dst_rad))
                        /(math.cos(latA)*math.sin(dst_rad)))
    if math.sin(lonB - lonA) > 0:
        return r2d(azm_rad)
    else:
        return 360 - r2d(azm_rad)

print('#####################################',
    '\n###   python3 station_inf_100km   ###',
    '\n#####################################')

# open the file of the parameters given by the user through parametres.py and
# load them
root_folder = os.getcwd()[:-6]
os.chdir(root_folder + '/Kumamoto')
with open('parametres_bin', 'rb') as my_fch:
    my_dpck = pickle.Unpickler(my_fch)
    param = my_dpck.load()

# all the parameters are not used, only the following ones
R_Earth = param['R_Earth']
event = param['event']

# directories used in this script:
# - path_data is the directory where all the records are stored in SAC format
# - path_results is where a copie of the records with hypocenter distance less
# than 100 km will be done
path_data = (root_folder + '/'
             + 'Kumamoto/'
             + event + '/'
             + 'acc/'
             + 'brut')
path_results = (root_folder + '/'
                + 'Kumamoto/'
                + event + '/'
                + 'acc/'
                + 'inf100km')

# create the directory path_results in case it does not exist
if not os.path.isdir(path_results):
    try:
        os.makedirs(path_results)
    except OSError:
        print('Creation of the directory {} failed'.format(path_results))
    else:
        print('Successfully created the directory {}'.format(path_results))
else:
    print('{} is already created'.format(path_results))

# load location of the studied earthquake
os.chdir(root_folder + '/Kumamoto')
with open('ref_seismes_bin', 'rb') as my_fich:
    my_depick = pickle.Unpickler(my_fich)
    dict_seis = my_depick.load()

lat_hyp = dict_seis[event]['lat']
lon_hyp = dict_seis[event]['lon']
dep_hyp = dict_seis[event]['dep']
hypo = [R_Earth - dep_hyp, lat_hyp, lon_hyp]

# here, we are dealing with two different networks:
# - K-NET: every geographical location has one station at the surface
# - KiK-net: every geographical location has two stations, one borehole and one
# at the surface and we consider only the ones at the surface to be consistent
# with the first network (for instance, the station S is related to EW1, NS1,
# UD1, EW2, NS2 and UD2 and we only consider EW2, NS2 and UD2 the three
# components recorded at the surface)
os.chdir(path_data)
list_stat = os.listdir(path_data)
list_stat_UD = [a for a in list_stat if ('UD' in a) and ('UD1' not in a)]
list_stat_NS = [a for a in list_stat if ('NS' in a) and ('NS1' not in a)]
list_stat_EW = [a for a in list_stat if ('EW' in a) and ('EW1' not in a)]
list_stat = list_stat_UD + list_stat_NS + list_stat_EW

print('Check the two values of the hypocenter distance and select those with',
        'hypocenter distance less than 100 km')
for s in list_stat:
    os.chdir(path_data)
    st = read(s)
    pos_sta = [R_Earth + 0.001*st[0].stats.sac.stel,
               st[0].stats.sac.stla,
               st[0].stats.sac.stlo]
    dst = dist(hypo, pos_sta)
    print('The station {}'.format(s[:6]),
    'with hypocenter distance equal to {:.1f}'.format(dst),
    '({:.1f})'.format(st[0].stats.sac.dist),
    end = ' ')
    if dst < 100:
        os.chdir(path_results)
        print('  --->  selected')
        st[0].stats.sac.dist = dst
        st[0].stats.sac.az = azim(hypo, pos_sta)
        tr = Trace(st[0].data, st[0].stats)
        tr.write(s, format='SAC')
    else:
        print('')
