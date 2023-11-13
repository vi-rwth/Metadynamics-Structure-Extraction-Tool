import numpy as np
import os
import sys
import time 
import itertools as it
import shapely.geometry
import copy
import tqdm
import multiprocessing as mp
import MDAnalysis as mda
import matplotlib.pyplot as plt
from matplotlib import ticker
import operator as op
import shutil
import warnings
import argparse
warnings.filterwarnings('ignore')
parser = argparse.ArgumentParser()

parser.add_argument('-traj', dest='traj', required=True, help='!REQUIRED! MD trajectory-file name in the MD-output-directory. Format is also used for output-files.', type=str)
parser.add_argument('-md', dest='md_dir', default=os.getcwd(), help='MD-output-directory path. DEFAULT: Current directory path.')
parser.add_argument('-thresh', dest='thresh', default=None, help='Specifies threshold for assigning. Input value has to correspond with values in FES-file. DEFAULT: Lowest 1/12 of the energy span.', type=float)
parser.add_argument('-topo', dest='topo', default=None, help='MD topology-file name in the MD-output-directory, if trajectory-file does not specify topology. DEFAULT: None.', type=str)
parser.add_argument('-fes', dest='fes', default='fes.dat', help='FES-file name in the MD-output-directory. DEFAULT: "fes.dat".', type=str)
parser.add_argument('-colv', dest='colvar', default='COLVAR', help='COLVAR-file in the MD-output-directory. DEFAULT: "COLVAR".')
parser.add_argument('-png', dest='fes_png', default=True, help='Specifies whether a PNG-visualization of the FES should be created. Expects True/False. DEFAULT: True.', type=bool)

args = parser.parse_args()

def init_worker_pdb(sorted_coords,a,b,lines,atom_count,head,desc,num_areas,barargs):
    tqdm.tqdm.set_lock(barargs)
    global Gsorted_coords
    global Ga
    global Gb
    global Gatom_count
    global Ghead
    global Glines
    global Gdesc
    global Gnum_areas
    Gatom_count, Ghead, Glines, Gsorted_coords, Ga, Gb, Gdesc, Gnum_areas = atom_count, head, lines, sorted_coords, a, b, desc, num_areas

def init_worker(sorted_coords,a,b,u,ag,desc,num_areas,barargs):
    tqdm.tqdm.set_lock(barargs)
    global Gsorted_coords
    global Ga
    global Gb
    global Gu
    global Gag
    global Gdesc
    global Gnum_areas
    Gsorted_coords, Ga, Gb, Gu, Gag, Gdesc, Gnum_areas = sorted_coords, a, b, u, ag, desc, num_areas
    
def init_polygon(all_points,tolerance,mp_sorted_coords, barargs):
    tqdm.tqdm.set_lock(barargs)
    global Gall_points
    global Gtolerance
    global managed_list
    Gall_points, Gtolerance, managed_list = all_points, tolerance, mp_sorted_coords
    
def det_min_frames(j):
    coords = []
    pos1 = mp.current_process()._identity[0]-2
    with tqdm.tqdm(total=len(all_points), desc='min ' + str(j), position=pos1, leave=False) as pbar:
        for i,point in enumerate(Gall_points):
            if polygons[j].distance(point) <= Gtolerance:
                coords.append([a[i],b[i]])
            pbar.update(1)
        managed_list.append(coords)

def have_common_elem(l1, l2):
    for elem in l2:
        if op.countOf(l1, elem) > 0:
            return True
            break
    return False

def group_numbers(numbers, max_diff):
    separate_groups, subgroup = [], []
    tmplist = copy.deepcopy(numbers)
    seed_elem = tmplist[0]
    with tqdm.tqdm(total=len(tmplist), desc='grouping outline', leave=False) as pbar:
        while any(tmplist):  
            min_distance = max_diff
            found = False
            try:
                tmplist.remove(seed_elem)
                new_group_found = False
            except ValueError:
                pass
            for compare_elem in tmplist: 
                if ((seed_elem[0]-compare_elem[0])**2 + (seed_elem[1]-compare_elem[1])**2)**0.5 < min_distance: 
                    found = True
                    min_distance = ((seed_elem[0]-compare_elem[0])**2 + (seed_elem[1]-compare_elem[1])**2)**0.5
                    min_elem = compare_elem
            if found == True and any(subgroup):
                if new_group_found == False:
                    subgroup.append(seed_elem)
                seed_elem = min_elem   
            else:
                if any(subgroup):  
                    separate_groups.append(subgroup)
                subgroup = []
                sec_run = False
                min_distance = max_diff
                for group in separate_groups:
                    for elem in group:
                        if  ((seed_elem[0]-elem[0])**2 + (seed_elem[1]-elem[1])**2)**0.5 < min_distance:
                            group.append(seed_elem)
                            sec_run = True
                            break
                    if sec_run == True:
                        break
                if sec_run == False:
                    subgroup.append(seed_elem)
                    new_group_found = True
                elif any(tmplist):
                    seed_elem = tmplist[0]
            pbar.update(1)
    return separate_groups

def sort(i):
    indx_list = []
    with open('min_overview.txt', 'a') as overviewfile:
        if Gdesc:
            overviewfile.writelines('min_' + str(i) + ': ' + Gdesc[i] + '\n')
        else:
            overviewfile.writelines('min_' + str(i) + ': '+ fes_var.split(' ')[pos_cvs_fes[0]+2] +': ' + str(round(np.mean(grouped_points[i], axis=0)[0],4)) + ' '+fes_var.split(' ')[pos_cvs_fes[1]+2]+': ' + str(round(np.mean(grouped_points[i], axis=0)[1],4)) + '\n')
    pos = mp.current_process()._identity[0]-2-Gnum_areas
    with tqdm.tqdm(total=len(Gsorted_coords[i]), desc='min ' + str(i) + ': ' + str(len(Gsorted_coords[i])) + ' frames', position=pos, leave=False) as progress_bar:
        for o in range(len(Gsorted_coords[i])):
            indx_a = np.where(Ga==Gsorted_coords[i][o][0])[0]
            indx_b = np.where(Gb==Gsorted_coords[i][o][1])[0]
            both = set(indx_a).intersection(indx_b)
            indx = both.pop()
            indx_list.append(indx)
            progress_bar.update(1)
    try:
        Gag.write('min_' + str(i) + '.' + args.traj.split('.')[1], frames=Gu.trajectory[indx_list])
    except (IndexError, NameError):
        if args.traj.endswith('.pdb'):
            tempfile = open('min_' + str(i) + '.pdb', 'w')
            ref_point = [0,0,0]
            for o,elem_inner in enumerate(indx_list):
                min_coords, shift_vect, print_out = [], [0,0,0], []
                count = it.count(0)
                for k in range(Ghead+(elem_inner*(Gatom_count+3)), Ghead+((elem_inner+1)*(Gatom_count+3))):
                    if Glines[k].startswith('ATOM'):
                        tmp_count = next(count)
                        print_lines = []
                        str_part_1 = Glines[k].split('                 ')[0]
                        str_part_2 = Glines[k].split('0.00  0.00')[1]
                        if not len(" ".join(Glines[k].split()).split(' ')) < 9:
                            atom_coords =[float(" ".join(Glines[k].split()).split(' ')[3]),float(" ".join(Glines[k].split()).split(' ')[4]),float(" ".join(Glines[k].split()).split(' ')[5])]
                        else:
                            if len(" ".join(Glines[k].split()).split(' ')[3]) > 8:
                                tmp_str = " ".join(Glines[k].split()).split(' ')[3].split('-')
                                if len(tmp_str) == 2:
                                    atom_coords = [float(tmp_str[0]),float(tmp_str[1])*(-1),float(" ".join(Glines[k].split()).split(' ')[4])]
                                elif len(tmp_str) == 4:
                                    atom_coords = [float(tmp_str[1])*(-1),float(tmp_str[2])*(-1),float(tmp_str[3])*(-1)]
                                else:
                                    if len(tmp_str[0]) == 0:
                                        atom_coords = [float(tmp_str[1])*(-1),float(tmp_str[2])*(-1),float(" ".join(Glines[k].split()).split(' ')[4])]
                                    else:
                                        atom_coords = [float(tmp_str[0]),float(tmp_str[1])*(-1),float(tmp_str[2])*(-1)]
                            elif len(" ".join(Glines[k].split()).split(' ')[4]) > 8:
                                tmp_str = " ".join(Glines[k].split()).split(' ')[4].split('-')
                                atom_coords = [float(" ".join(Glines[k].split()).split(' ')[3]),float(tmp_str[0]),float(tmp_str[1])*(-1)]
                        if o == 0 and tmp_count == 0:
                            ref_point = atom_coords
                        if not o == 0 and tmp_count == 0:
                            shift_vect = (np.array(ref_point) - np.array(atom_coords))
                        min_coords.append((np.array(atom_coords) + np.array(shift_vect)).tolist())
                        print_lines = ''.join((str_part_1,' '*(25-len(str(round(min_coords[tmp_count][0],3)))),str(round(min_coords[tmp_count][0],3)),' '*(8-len(str(round(min_coords[tmp_count][1],3)))),str(round(min_coords[tmp_count][1],3)),' '*(8-len(str(round(min_coords[tmp_count][2],3)))),str(round(min_coords[tmp_count][2],3)),'  0.00  0.00',str_part_2))  
                        print_out.append(print_lines)
                    elif Glines[k].startswith('REMARK'):
                        print_out.append(Glines[k])
                    elif Glines[k].startswith('CRYST1'):
                        print_out.append(Glines[k])                
                print_out.append('END\n')           
                tempfile.writelines(print_out) 
            tempfile.close()
        else:
            raise Exception('Multiple frames are not supported with this trajectory-format.')
    except (TypeError, ValueError):
        print('MDAnalysis does not support writing in ' + args.traj.split('.')[1] + '-format, writing in xyz-format instead')
        Gag.write('min_' + str(i) + '.xyz', frames=Gu.trajectory[indx_list])

def sort_pdb_cp2k_prework():
    with open(args.traj, 'r+') as f:
        lines = f.readlines()
    atom_count, head = 0, 0
    for line in lines:
        if line.startswith('ATOM'):
            atom_count += 1
        elif line.startswith('END'):
            break
        elif line.startswith('AUTHOR') or line.startswith('TITLE'):
            head += 1
    return head, atom_count, lines

if __name__ == '__main__':
    print('                                                   ')
    print('.: Metadynamics Structure Extraction Tool - MSET :.')
    print('           .: Multiprocessing version :.           ')
    print('                                                   ')
    print('working on directory: ' + args.md_dir)
    outline = []
    count1, count2 = it.count(0), it.count(0)
    thresh_val, tot_min_frames, dimX, dimY = 0, 0, 0, 1
    os.chdir(args.md_dir)

    with open(args.colvar, 'r') as colvar_file:
        col_var = colvar_file.readline()
    with open(args.fes, 'r') as fes_file:
        fes_var = fes_file.readline()
    pos_ener = fes_var.split(' ').index('file.free')-2
    com = list(set(col_var.split(' ')).intersection(fes_var.split(' ')))
    pos_cvs_fes, pos_cvs_col = [], []
    for elem in com:
        if not elem == '#!' and not elem == 'FIELDS':
            pos_cvs_fes.append(fes_var.split(' ').index(elem)-2)
            pos_cvs_col.append(col_var.split(' ').index(elem)-2)            
    pos_cvs_fes.sort()
    pos_cvs_col.sort()
    
    if not len(pos_cvs_fes) == 2 or not len(pos_cvs_col) == 2:
        raise Exception('Only MD-runs with 2 CVs supported')
    
    data_fes = np.genfromtxt(args.fes)
    data_fes_T = np.transpose(data_fes)
    a_fes, b_fes, ener = data_fes_T[pos_cvs_fes[0]].copy(), data_fes_T[pos_cvs_fes[1]].copy(), data_fes_T[pos_ener].copy()
    
    for i in range(len(ener)):
        if not np.isfinite(ener[i]):
            raise Exception('Non-finite value (NaN or inf) discovered in FES-file')
    
    if args.thresh == None:
        thresh_val = max(ener) - abs(max(ener)-min(ener))*(1-1/12)
        print('automatically determined', end =' ') 
    else:
        thresh_val = args.thresh
    print('threshold value: ' + str(round(thresh_val,3)) + ' a.U.')
        
    b_count = b_fes[0]
    for elem in b_fes:
        if not elem == b_count:
            dimY += 1
            b_count = elem    
    while b_fes[next(count1)] == b_fes[0]:
        dimX += 1
    low_max_a, high_max_a, low_max_b, high_max_b = a_fes[0], a_fes[dimX-1], b_fes[0], b_fes[-1]
    outline_show_a, outline_show_b, edge = [], [], []
    
    for i in tqdm.tqdm(range(len(ener)),desc='collecting outline', leave=False):
        try:
            if ener[i]<thresh_val and (a_fes[i] == low_max_a or a_fes[i] == high_max_a or b_fes[i] == low_max_b or b_fes[i] == high_max_b or ener[i-1]>thresh_val or ener[i+1]>thresh_val or ener[i-dimX]>thresh_val or ener[i+dimX]>thresh_val):
                if a_fes[i] == low_max_a or a_fes[i] == high_max_a or b_fes[i] == low_max_b or b_fes[i] == high_max_b:
                    edge.append([a_fes[i],b_fes[i]])
                outline.append([a_fes[i],b_fes[i]])
                outline_show_a.append(abs((a_fes[i]-low_max_a)/((high_max_a-low_max_a)/dimX)))
                outline_show_b.append(dimY-abs((b_fes[i]-low_max_b)/((high_max_b-low_max_b)/dimY)))
        except IndexError:
            pass
        
    tolerance = abs(a_fes[0]-a_fes[1])/2     
    data_colvar = np.genfromtxt(args.colvar)
    data_colvar_T = np.transpose(data_colvar)
    a, b = data_colvar_T[pos_cvs_col[0]].copy(), data_colvar_T[pos_cvs_col[1]].copy()

    try:
        if args.topo == None:
            u = mda.Universe(args.traj, in_memory=True)
        else:
            u = mda.Universe(args.topo, args.traj, in_memory=True)
        ag =u.select_atoms('all')
        if not len(u.trajectory) == len(a):
            raise Exception('COLVAR-file and trajectory-file must have similar step length, here' + str(len(a)) + ' vs ' + str(len(u.trajectory)))
    except IndexError:
        if args.traj.endswith('.pdb'):
            head, atom_count, lines = sort_pdb_cp2k_prework()
            if not (len(lines)-head)/(atom_count+3) == len(a):
                raise Exception('COLVAR-file and trajectory-file must have similar step length, here: ' + str(len(a)) + ' vs ' + str((len(lines)-head)/(atom_count+3)))
        else:
            raise Exception('MDAnalysis does not support the topology- or trajectory-file')
    except FileNotFoundError:
        raise

    all_points = [shapely.geometry.Point(a[i],b[i]) for i in range(len(a))]        
    grouped_points = group_numbers(outline, 20*np.sqrt(8)*tolerance)

    start1 = time.perf_counter()
    polygons = [shapely.geometry.Polygon(groups) for groups in grouped_points]
        
    periodicity = False
    if edge:
        edge_points, pbc = [], []
        grouped_edges = group_numbers(edge, 10*np.sqrt(8)*tolerance)
        for i,group1 in enumerate(grouped_edges):
            if sum(list(map(len, pbc))) >= len(grouped_edges):
                break
            expect_group, tmp_lst = [], []
            for elem in group1:
                tmp_pt = copy.deepcopy(elem)
                if elem[0] == high_max_a:
                    tmp_pt[0] = low_max_a
                elif elem[0] == low_max_a:
                    tmp_pt[0] = high_max_a
                if elem[1] == high_max_b:
                    tmp_pt[1] = low_max_b
                elif elem[1] == low_max_b:
                    tmp_pt[1] = high_max_b
                expect_group.append(tmp_pt)
            found_periodic = False
            for j,group2 in enumerate(grouped_points):
                if have_common_elem(group2, expect_group) or have_common_elem(group2, group1):
                    periodicity = True
                    found_periodic = True
                    tmp_lst.append(j)
            if found_periodic == True:
                if len(tmp_lst) == 1:
                    break
                elif i == 0:
                    print('periodicity detected: boundaries will be considered periodic')
                pbc.append(tmp_lst)
    print(str(len(polygons)), end = ' ')
    if periodicity == True:
        print('distinctive areas identified')
    else:
        print('minima identified')
    
    tot_min_frames =0
    if len(polygons) > os.cpu_count()-1:
        usable_cpu = os.cpu_count()-1
    else:
        usable_cpu = len(polygons)
    manager = mp.Manager()
    mp_sorted_coords = manager.list()
    with mp.Pool(processes=usable_cpu, initializer=init_polygon, initargs=(all_points, tolerance, mp_sorted_coords, mp.RLock(),)) as pool:
        pool.map(det_min_frames, range(len(polygons)))
    sorted_coords = list(mp_sorted_coords)
    for lists in sorted_coords:
        tot_min_frames += len(lists)
    print(' processed ' + str(len(a)) + ' frames')
    print('found ' + str(tot_min_frames) + ' minima frames')
    print('time needed for minima frames identification step: ' + str(round(time.perf_counter() - start1,3)) + ' s')
    
    desc = []
    if periodicity == True:
        sorted_coords_period, tot_pbc  = [], []
        for elem in pbc:
            desc.append(' + '.join((fes_var.split(' ')[pos_cvs_fes[0]+2] + ': ' + str(round(np.mean(grouped_points[j], axis=0)[0],4)) + ' '+fes_var.split(' ')[pos_cvs_fes[1]+2]+': ' + str(round(np.mean(grouped_points[j], axis=0)[1],4))) for j in elem))
            help_list = []
            for i in elem:
                tot_pbc.append(i)
                help_list += sorted_coords[i]
            sorted_coords_period.append(help_list)
        for i,elem in enumerate(sorted_coords):
            if not i in tot_pbc:
                desc.append(fes_var.split(' ')[pos_cvs_fes[0]+2]+': ' + str(round(np.mean(grouped_points[i], axis=0)[0],4)) + ' '+fes_var.split(' ')[pos_cvs_fes[1]+2]+': ' + str(round(np.mean(grouped_points[i], axis=0)[1],4)))
                sorted_coords_period.append(elem)
        sorted_coords = sorted_coords_period
        print(str(len(sorted_coords)) + ' minima identified')

    try:
        os.mkdir('minima')
    except FileExistsError:
        shutil.rmtree('minima')
        os.mkdir('minima')
    
    os.chdir('minima')
    with open('min_overview.txt', 'w') as overviewfile:
        pass
    
    if args.fes_png == True:
        bins = np.empty((dimY,dimX))
        for i in range(dimY):
            for l in range(dimX):
                bins[-1-i,l] = ener[next(count2)]
    
        plt.figure(figsize=(8,6), dpi=100)
        plt.imshow(bins, interpolation='gaussian', cmap='nipy_spectral')
        plt.xticks(np.linspace(-0.5,dimX-0.5,5),np.round(np.linspace(low_max_a,high_max_a, num=5),3))
        plt.yticks(np.linspace(-0.5,dimY-0.5,5),np.round(np.linspace(high_max_b,low_max_b, num=5),3))
        plt.xlabel(fes_var.split(' ')[pos_cvs_fes[0]+2] + ' [a.U.]')
        plt.ylabel(fes_var.split(' ')[pos_cvs_fes[1]+2] + ' [a.U.]')
        plt.axis('tight')
        plt.title('threshold: ' + str(round(thresh_val,3)) + ' a.U.')
        plt.plot(outline_show_a, outline_show_b, '.', color='white')
        cb = plt.colorbar(label='free energy [a.U.]', format="{x:.0f}")
        tick_locator = ticker.MaxNLocator(nbins=8)
        cb.locator = tick_locator
        cb.update_ticks()    
        plt.savefig('fes_visual.png',bbox_inches='tight')
    
    if len(sorted_coords) > os.cpu_count()-1:
        usable_cpu = os.cpu_count()-1
    else:
        usable_cpu = len(sorted_coords)
    
    start3 = time.perf_counter()
    try:
        pool = mp.Pool(processes = usable_cpu, initializer=init_worker, initargs=(sorted_coords,ab_tuple,u,ag,desc,len(polygons),mp.RLock(),)) 
    except NameError:
        pool = mp.Pool(processes = usable_cpu, initializer=init_worker_pdb, initargs=(sorted_coords,a,b,lines,atom_count,head,desc,len(polygons),mp.RLock(),))
    out = pool.map(sort, range(len(sorted_coords)))
    pool.close()
    pool.join()

    print(' time needed for postprocessing step: ' + str(round(time.perf_counter() - start3,3)) + ' s')
    
    print('                                                   ')
    print('           .: terminated successfully :.           ')