#!/usr/bin/python3
#-*- coding: utf-8 -*-
import os
import sys
from subprocess import Popen, PIPE, STDOUT
import subprocess
import timeit
import json
from datetime import datetime

def human_bytes(B):
    """Return human readable file unit like KB, MB, GB string by Byte
    Args:
        B : input byte values
    Returns:
        KB / MB / GB
    """
    B = float(B)
    KB = float(1024)
    MB = float(KB ** 2) # 1,048,576
    GB = float(KB ** 3) # 1,073,741,824
    TB = float(KB ** 4) # 1,099,511,627,776

    if B < KB:
        return '{0} {1}'.format(B,'Bytes' if 0 == B > 1 else 'Byte')
    elif KB <= B < MB:
        return '{0:.2f} KB'.format(B/KB)
    elif MB <= B < GB:
        return '{0:.2f} MB'.format(B/MB)
    elif GB <= B < TB:
        return '{0:.2f} GB'.format(B/GB)

def get_pvc_info():
    """Return namespace, pv name, volumeName for filtering PVC in kubernetes cluster
    Filter condition
        - Is it Bound?
        - Is it StorageClass efs?
        - 
    """

    info_pvc_cmd = "kubectl get pvc --all-namespaces -o json | jq -r '.items[] | select( ( .spec.storageClassName | contains(" + '"' + "efs" + '"' + ") ) and ( .status.phase | contains(" + '"' + "Bound" + '"' + ") ) )' | jq -r '.metadata.namespace, .metadata.name, .spec.volumeName'"
    info_pvc = Popen(info_pvc_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    info_pvc_list = info_pvc.stdout.read().decode('utf-8').split()
    count=3
    info_pvc_list = [ info_pvc_list[i:i+count] for i in range(0,len(info_pvc_list),count) ]
    return info_pvc_list

def get_efs_provisioner():
    efs_provisioner_cmd = "kubectl get pod -n kube-system | grep efs | awk '{print $1}'"
    efs_provisioner_res = Popen(efs_provisioner_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    efs_provisioner_id = efs_provisioner_res.stdout.read().decode('utf-8').replace('\n','')
    return efs_provisioner_id

def get_pv_name():
    """Return pv name in kubernetes cluster
    """
    
    pv_id_cmd = "kubectl exec -it "+get_efs_provisioner()+ " -n kube-system -- ls -al /persistentvolumes | awk '{print $9}' | sed '1,3d'"
    pv_id_res = Popen(pv_id_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    pv_id_list = pv_id_res.stdout.readlines()[1:]
    return pv_id_list

def match_collect_info():
    """Return volume size matching pv id and efs directory's name which is exactly same.
    """
    info_list=get_pvc_info()
    pv_list=get_pv_name()

    size_pvc=[]
    metric_list = []

    for pv_name in pv_list:
        for i_group in info_list:
            i_name=i_group[1]+'-'+i_group[2]
            if pv_name.decode('utf-8').replace('\n','') == i_name:
                # Calculate volume size
                m_size_cmd = "kubectl exec -it "+get_efs_provisioner()+" -n kube-system -- du -ks /persistentvolumes/" + pv_name.decode('utf-8').replace('\n','') + " | awk '{print $1}'"
                m_size_res = Popen(m_size_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
                m_size = m_size_res.stdout.readlines()[1:]
                sum_size = human_bytes(int(m_size[0].decode('utf-8').replace('\n',''))*1024)
                size_pvc.append(sum_size)

                # Find pod name for using claim name
                find_pod_name_cmd = "kubectl get pod -n "+ i_group[0] +" | grep "+ i_group[1] + " | awk '{print $1}'"
                find_pod_name_res = Popen(find_pod_name_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
                find_pod_name = find_pod_name_res.stdout.read().decode('utf-8').replace('\n','')
                
                if find_pod_name and find_pod_name != "No resources found.":
                    metric_info = {"namespace":i_group[0], "name":find_pod_name, "size":str(sum_size), "pvc":pv_name.decode('utf-8').replace('\n','')}
                    metric_list.append(metric_info)
    return metric_list

def all_efs_collect_info():
    """Return all efs directory volumes size
    It needs to calculate all pvc which isn't detecting 'match_collect_info' function.
    Because there are not usable pvc's in there and we need to find and destroy.
    """
    pv_list=get_pv_name()

    size_pvc = []
    metric_list = []


    for pv_name in pv_list:
        all_size_cmd = "kubectl exec -it "+get_efs_provisioner()+" -n kube-system -- du -ks /persistentvolumes/"+ pv_name.decode('utf-8').replace('\n','') + " | awk '{print $1}'"
        all_size_res = Popen(all_size_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        all_size = all_size_res.stdout.readlines()[1:]
        all_sum_size = human_bytes(int(all_size[0].decode('utf-8').replace('\n',''))*1024)
        size_pvc.append(all_sum_size)

        metric_info = {"pvc":pv_name.decode('utf-8').replace('\n',''), "size":str(all_sum_size)}
        metric_list.append(metric_info)
    return metric_list

if __name__ == "__main__":
    """
    Collect pvc size, pvc name, namespace, pod name.
    It uses 'kubectl' command for executing command 'kubectl exec' and 'du' command for finding size how much pods are using.
    It uses 'exec' command that exporter gets inside to pods and collect files, directories size.
    But it failed because prometheus server can't use '/bin/bash' or '/bin/sh', so it du / df command didn't work.
    So find directories list in /persistentvolumes/
    """

    datetime_now = datetime.now() # Define current time
    start = timeit.default_timer() # Record processing time
    json_info = {"timestamp":str(datetime_now), "metadata":{"matching":match_collect_info(), "all":all_efs_collect_info()}}
    
    print(json.dumps(json_info))

    stop = timeit.default_timer()
    laptime=stop-start

    print('\nlaptime = '+str(laptime))