#!/usr/bin/python
import os
import sys
from subprocess import Popen, PIPE, STDOUT
import subprocess
import timeit
import json
from datetime import datetime


def get_info():
    """Return name, namespace, volumeName for PVC in kubernetes cluster
    Args:
        None
    Returns:
        all info for list
        [[name],[namespace],[pvc id]]
    """
    
    #info_pre = subprocess.check_output("kubectl get pvc --all-namespaces -o json | jq ' .items[].metadata.name, .items[].metadata.namespace, .items[].spec.volumeName'", shell=True)
    info_pre_cmd = "kubectl get pvc --all-namespaces -o json | jq ' .items[].metadata.name, .items[].metadata.namespace, .items[].spec.volumeName'"
    info_pre = Popen(info_pre_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    info_pre_list = info_pre.stdout.read().replace('"','').split()
    info_count=len(info_pre_list)/3
    
    cnt = 0
    get_namespace, get_pvc_name, get_pvc_id = ([] for i in range(3)) # Define get_namespace, get_pvc_name, get_pvc_id

    for arg in info_pre_list:
        if info_count > cnt:
            get_pvc_name.append(arg)
        elif info_count*2 > cnt and info_count <= cnt:
            get_namespace.append(arg)
        elif info_count*3 > cnt and info_count*2 <= cnt:
            get_pvc_id.append(arg)
        cnt=cnt+1
    
    return [get_namespace, get_pvc_name, get_pvc_id]


def collect_info():

    namespaces, pvc_names, pvc_ids = get_info() # namespaces, pvc_names, pvc_ids are list

    if not namespaces:
        print("Warning : Can't find namespaces \n"
            "You should check authorization in kubernetes cluster \n")
    else:
        get_efs_provisioner_name = Popen("kubectl get pod -n kube-system | grep efs | awk '{print $1}'", shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        efs_provisioner_name = get_efs_provisioner_name.stdout.read().replace('\n','')
        
        metric_list = [] # Define metric list
        datetime_now = datetime.now() # Define current time

        """
        Collect size of pvc which mount each pods.
        List directories in 'persistentvolumes' directory and use 'du' command for collecting pvc size.
        """
        for val in range(len(namespaces)):
            find_dir_cmd = "kubectl exec -it " + efs_provisioner_name + " -n kube-system -- ls -al /persistentvolumes | awk '{print $9}' | grep " + pvc_names[val] + "-" + pvc_ids[val]

            try:
                find_dir = Popen(find_dir_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
                find_dir = find_dir.stdout.read()
            except subprocess.CalledProcessError as ex:
                # output = ex.output
                returncode = ex.returncode
                if returncode != 1:
                    raise

            if find_dir:
                pod_name_cmd = "kubectl describe pvc -n " + namespaces[val] + " " + pvc_names[val] + " | grep Mounted | awk '{print $3}'" # pod name
                pod_name = Popen(pod_name_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
                pod_name = pod_name.stdout.read()

                if 'none' not in pod_name.replace('\n',''):
                    """
                    It has a bug --> du caculate too late some of kubernetes cluster and then tty timeout. So it doesn't calculate.
                    Using command for 'du' is like this.
                    
                    cmd --> mount_size_cmd = "kubectl exec -it " + efs_provisioner_name + " -n kube-system -- du -c -hs /persistentvolumes/" + pvc_names[val] + "-" + pvc_ids[val] + " | awk '{print $1}'"
                    """
                    
                    find_file_list_cmd = "kubectl exec -it " +efs_provisioner_name + " -n kube-system -- ls -al /persistentvolumes/" + pvc_names[val] + "-" + pvc_ids[val] + " | awk '{print $9}'" # find list
                    find_file_list = Popen(find_file_list_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
                    if find_file_list.stdout.readline() != "Unable to use a TTY - input is not a terminal or the right kind of file" or find_file_list.stdout.readline() != "." or find_file_list.stdout.readline() != ".." or "No such file or directory" not in find_file_list.stdout.readline():
                        find_file_list = find_file_list.stdout.readline()

                        if len(find_file_list) > 1:
                            mount_size=[]
                            for _file in find_file_list:
                                m_size_cmd = "kubectl exec -it " + efs_provisioner_name + " -n kube-system -- du -ks /persistentvolumes/" + pvc_names[val] + "-" + pvc_ids[val] + "/" + _file + " | awk '{print $1}'"
                                m_size = Popen(m_size_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
                                m_size=m_size.stdout.read().split()
                                mount_size.append(''.join(m_size))
                            mount_size = list(map(int, mount_size))
                            
                            sum_size = sum(mount_size)
                            sum_size = human_bytes(sum_size*1024)
                            
                            metric_info = {"namespace":namespaces[val], "name":pod_name.replace('\n',''), "size":str(sum_size), "pvc":pvc_names[val]}
                            metric_list.append(dict(metric_info))

                            #print("EFS PVC Monitor >> " + " namespace = " + namespaces[val] + "/ pod name = " + pod_name.replace('\n','') + "/ PVC size =  " + str(sum_size))
                        else:
                            metric_info = {"namespace":namespaces[val], "name":pod_name.replace('\n',''), "size":"4KB", "pvc":pvc_names[val]}
                            metric_list.append(dict(metric_info))

                        #print("EFS PVC Monitor >> " + " namespace = " + namespaces[val] + "/ pod name = " + pod_name.replace('\n','') +" / PVC size =  " + "4KB")

        json_info = {"timestamp":str(datetime_now),"metadata":{ "pod":metric_list } } # Before change json type
        return json_info

if __name__ == "__main__":
    start = timeit.default_timer() # Record processing time

    json_info = collect_info()

    print(json.dumps(json_info))

    stop = timeit.default_timer()
    laptime=stop-start

    print('\nlaptime = ' + str(laptime))