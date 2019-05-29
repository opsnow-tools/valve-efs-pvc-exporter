#!/usr/bin/python
import os
import sys
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

def get_info():
    """Return name, namespace, volumeName for PVC in kubernetes cluster
    Args:
        None
    Returns:
        all info for list
        [[name],[namespace],[pvc id]]
    """
    
    info_pre = subprocess.check_output("kubectl get pvc --all-namespaces -o json | jq ' .items[].metadata.name, .items[].metadata.namespace, .items[].spec.volumeName'", shell=True)
    info_pre_list = info_pre.decode("utf-8").replace('"','').split()
    print(info_pre.decode("utf-8"))
    print(info_pre.decode("utf-8").replace('"',''))
    info_count=len(info_pre_list)
    
    cnt = 0
    get_namespace, get_pvc_name, get_pvc_id = ([] for i in range(3)) # Define get_namespace, get_pvc_name, get_pvc_id

    for arg in info_pre_list:
        if info_count > cnt:
            get_pvc_name.append(arg)
        elif info_count*2 > cnt and info_count <= cnt:
            get_namespace.append(arg)
        elif info_count*3 > cnt and info_count*2 <= cnt:
            get_pvc_id.append(arg)
        else:
            print("Out of index")
        cnt=cnt+1
    
    return [get_namespace, get_pvc_name, get_pvc_id]

def collect_info():

    namespaces, pvc_names, pvc_ids = get_info() # namespaces, pvc_names, pvc_ids are list

    if not namespaces:
        print("Warning : Can't find namespaces \n"
            "You should check authorization in kubernetes cluster \n")
    else:
        get_efs_provisioner_name = subprocess.check_output("kubectl get pod -n kube-system | grep efs | awk '{print $1}'", shell=True)
        efs_provisioner_name = get_efs_provisioner_name.decode("utf-8").replace('\n','')
        
        metric_list = [] # Define metric list
        datetime_now = datetime.now() # Define current time

        """
        Collect size of pvc which mount each pods.
        List directories in 'persistentvolumes' directory and use 'du' command for collecting pvc size.
        """
        for val in range(len(namespaces)):
            find_dir_cmd = "kubectl exec -it " + efs_provisioner_name + " -n kube-system -- ls -al /persistentvolumes | awk '{print $9}' | grep " + pvc_names[val] + "-" + pvc_ids[val]

            try:
                find_dir = subprocess.check_output(find_dir_cmd, shell=True)
                find_dir = find_dir.decode("utf-8")
            except subprocess.CalledProcessError as ex:
                # output = ex.output
                returncode = ex.returncode
                if returncode != 1:
                    raise

            if find_dir:
                pod_name_cmd = "kubectl describe pvc -n " + namespaces[val] + " " + pvc_names[val] + " | grep Mounted | awk '{print $3}'" # pod name
                pod_name = subprocess.check_output(pod_name_cmd, shell=True)
                pod_name = pod_name.decode("utf-8")

                if 'none' not in pod_name.replace('\n',''):
                    """
                    It has a bug --> du caculate too late some of kubernetes cluster and then tty timeout. So it doesn't calculate.
                    Using command for 'du' is like this.
                    
                    cmd --> mount_size_cmd = "kubectl exec -it " + efs_provisioner_name + " -n kube-system -- du -c -hs /persistentvolumes/" + pvc_names[val] + "-" + pvc_ids[val] + " | awk '{print $1}'"
                    """
                    
                    find_file_list_cmd = "kubectl exec -it " +efs_provisioner_name + " -n kube-system -- ls -al /persistentvolumes/" + pvc_names[val] + "-" + pvc_ids[val] + " | awk '{print $9}' | sed -r \"s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[mGK]//g\"" # find list
                    find_file_list = subprocess.check_output(find_file_list_cmd, shell=True)
                    find_file_list = find_file_list.decode("utf-8").split()
                    find_file_list.remove('.')
                    find_file_list.remove('..')

                    if len(find_file_list) != 0:
                        mount_size=[]
                        for _file in find_file_list:
                            m_size_cmd = "kubectl exec -it " + efs_provisioner_name + " -n kube-system -- du -ks /persistentvolumes/" + pvc_names[val] + "-" + pvc_ids[val] + "/" + _file + " | awk '{print $1}'"
                            m_size = subprocess.check_output(m_size_cmd, shell=True)
                            m_size=m_size.decode("utf-8").split()
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
    """
    Collect pvc size, pvc name, namespace, pod name.
    It uses 'kubectl' command for executing command 'kubectl exec' and 'du' command for finding size how much pods are using.
    It uses 'exec' command that exporter gets inside to pods and collect files, directories size.
    But it failed because prometheus server can't use '/bin/bash' or '/bin/sh', so it du / df command didn't work.
    So find directories list in /persistentvolumes/
    """

    start = timeit.default_timer() # Record processing time

    json_info = collect_info()

    print(json.dumps(json_info))

    stop = timeit.default_timer()
    laptime=stop-start

    print('\nlaptime = ' + str(laptime))
    
    '''
    [ec2-user@seoul-dev-okc1-bastion ~]$ k get pvc --all-namespaces
    NAMESPACE   NAME                                   STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
    default     sample-efs                             Bound    pvc-8ed49a62-7ab8-11e9-a710-021602437252   1Gi        RWX            efs            5h33m
    devops      chartmuseum                            Bound    pvc-2ce33d40-54fc-11e9-bb58-0a3c8e8c39c4   8Gi        RWO            efs            48d
    devops      docker-registry                        Bound    pvc-43ac4e47-54fc-11e9-b369-02dc733572aa   20Gi       RWO            efs            48d
    devops      gocd-server                            Bound    pvc-e4332f8f-4085-11e9-bb58-0a3c8e8c39c4   2Gi        RWO            efs            74d
    devops      sonarqube-postgresql                   Bound    pvc-1d32e9b4-5512-11e9-b369-02dc733572aa   8Gi        RWO            efs            48d
    devops      sonarqube-sonarqube                    Bound    pvc-1ccdfd12-5512-11e9-b369-02dc733572aa   10Gi       RWO            efs            48d
    devops      sonatype-nexus-data                    Bound    pvc-2f3d76ab-5512-11e9-b369-02dc733572aa   30Gi       RWO            efs            48d
    devops      sonatype-nexus-data-sonatype-nexus-0   Bound    pvc-305de441-5512-11e9-b369-02dc733572aa   30Gi       RWO            efs            48d
    monitor     data-alertnow-rabbit-rabbitmq-0        Bound    pvc-357b798f-5c3f-11e9-8243-0afa1e2c6f72   8Gi        RWO            gp2            39d
    monitor     grafana                                Bound    pvc-350192ea-456d-11e9-bb58-0a3c8e8c39c4   5Gi        RWO            efs            68d
    monitor     prometheus-alertmanager                Bound    pvc-424ac2db-3e38-11e9-adea-0278c3cf8520   2Gi        RWO            efs            77d
    monitor     prometheus-server                      Bound    pvc-41ddc835-3e38-11e9-adea-0278c3cf8520   8Gi        RWO            efs            77d
    '''

    '''
    [ec2-user@seoul-dev-okc1-bastion test]$ k get pod --all-namespaces
    NAMESPACE           NAME                                                              READY   STATUS             RESTARTS   AGE
    alertnow-dev        alertnow-consumer-6854784bbb-67qc5                                1/1     Running            0          3d5h
    alertnow-dev        alertnow-escalator-7896f46b9d-gbbp9                               0/1     CrashLoopBackOff   498        3d1h
    alertnow-dev        alertnow-extension-6d6b859f9-b6mw2                                0/1     CrashLoopBackOff   12         40m
    alertnow-dev        alertnow-extension-7b4fb75957-k7m2b                               0/1     CrashLoopBackOff   9          63m
    alertnow-dev        alertnow-externalapi-5fc8b6b645-g5n74                             1/1     Running            0          3d1h
    alertnow-dev        alertnow-incidentapi-8b5b8d6db-87rfq                              1/1     Running            0          4h36m
    alertnow-dev        alertnow-postman-57c8496fcb-4wf7g                                 1/1     Running            0          4h36m
    alertnow-dev        alertnow-producer-79477fbd47-42vxb                                1/1     Running            0          4h36m
    alertnow-dev        alertnow-syncbatch-alertnow-dev-6564c85955-4gfxv                  1/1     Running            0          12d
    alertnow-dev        alertnow-syncbatch-alertnow-dev-6564c85955-zq5zq                  1/1     Running            0          12d
    alertnow-dev        alertnow-webapps-64fdf4fdf4-sbks9                                 1/1     Running            0          36m
    asset-dev           asset-assetclient-asset-dev-685454c8dc-4kdzk                      1/1     Running            0          73d
    bb8-onepack-dev     bb8-onepack-opsnow-front-bb8-onepack-dev-86496448bb-hrt86         1/1     Running            0          59d
    bb8-onepack-dev     bb8-onepack-opsnow-fulfillment-bb8-onepack-dev-799cd5c559-5jvv5   1/1     Running            0          24d
    bb8-onepack-stage   bb8-onepack-opsnow-front-bb8-onepack-stage-5db9cddfd-s9dbf        1/1     Running            0          59d
    brand-dev           brand-front-794fc46569-847hm                                      1/1     Running            0          5h2m
    brand-dev           brand-fulfill-584778dbb-bsw9r                                     1/1     Running            0          7d8h
    brand-dev           brand-fulfill-584778dbb-cq9lw                                     1/1     Running            0          7d8h
    brand-dev           brand-proxy-5df4f56df9-8sjns                                      1/1     Running            2          7d8h
    brand-dev           brand-proxy-5df4f56df9-t57xz                                      1/1     Running            2          7d5h
    brand-stage         brand-front-9448974b4-985tf                                       1/1     Running            0          7d5h
    brand-stage         brand-fulfill-6ff66658d5-8vx64                                    1/1     Running            0          7d8h
    brand-stage         brand-fulfill-6ff66658d5-wmz2w                                    1/1     Running            0          7d8h
    brand-stage         brand-proxy-6578f4f668-8p2mx                                      1/1     Running            2          7d5h
    cost-dev            cost-meteringclient-cost-dev-685799c5cd-8v5dq                     1/1     Running            0          73d
    demo-dev            demo-chatbot-85849fbfc7-nc4tz                                     1/1     Running            0          4h36m
    demo-stage          demo-chatbot-95c559b6d-pgwxr                                      1/1     Running            0          4h36m
    devops              argo-ui-6df999b6ff-vph9d                                          1/1     Running            0          16d
    devops              argo-workflow-controller-69ff6cc6bf-sh79v                         1/1     Running            0          16d
    devops              argocd-application-controller-f8b64874-m5hdg                      1/1     Running            2          13d
    devops              argocd-dex-server-5bb76b755b-84x5j                                1/1     Running            0          13d
    devops              argocd-redis-756d49f949-zskjm                                     1/1     Running            0          13d
    devops              argocd-repo-server-865958654-9mhlq                                1/1     Running            0          13d
    devops              argocd-server-8f6bf6897-x2hp4                                     1/1     Running            0          13d
    devops              chartmuseum-76cf5d67c5-hplvt                                      1/1     Running            0          48d
    devops              docker-registry-6f89666879-hrd6m                                  1/1     Running            0          48d
    gov-dev             gov-api-868b75b6df-49cbw                                          1/1     Running            0          178m
    gov-dev             gov-client-56bb948d76-qmn4r                                       1/1     Running            0          153m
    kube-ingress        nginx-ingress-controller-5687cd5b4-8tz4c                          1/1     Running            0          16d
    kube-ingress        nginx-ingress-controller-5687cd5b4-9ghfw                          1/1     Running            0          4d8h
    kube-ingress        nginx-ingress-controller-5687cd5b4-9ht5g                          1/1     Running            0          12d
    kube-ingress        nginx-ingress-controller-5687cd5b4-j89ts                          1/1     Running            0          16d
    kube-ingress        nginx-ingress-controller-5687cd5b4-ksxhh                          1/1     Running            0          6d2h
    kube-ingress        nginx-ingress-controller-5687cd5b4-md65v                          1/1     Running            0          11d
    kube-ingress        nginx-ingress-controller-5687cd5b4-rgb7f                          1/1     Running            0          13d
    kube-ingress        nginx-ingress-controller-5687cd5b4-sqdbt                          1/1     Running            1          7d8h
    kube-ingress        nginx-ingress-controller-5687cd5b4-vqqfv                          1/1     Running            0          6d1h
    kube-ingress        nginx-ingress-controller-5687cd5b4-vxl7g                          1/1     Running            0          7d8h
    kube-ingress        nginx-ingress-controller-5687cd5b4-zctdt                          1/1     Running            0          4d8h
    kube-ingress        nginx-ingress-default-backend-544cfb69fc-blqbr                    1/1     Running            0          76d
    kube-ingress        nginx-ingress-private-controller-6f99f54b54-44b48                 1/1     Running            0          17d
    kube-ingress        nginx-ingress-private-controller-6f99f54b54-t69qd                 1/1     Running            0          17d
    kube-ingress        nginx-ingress-private-default-backend-6757b6b59f-w2k5s            1/1     Running            0          17d
    kube-system         aws-node-5jcd4                                                    1/1     Running            1          77d
    kube-system         aws-node-8mgl6                                                    1/1     Running            0          45d
    kube-system         aws-node-l9wcn                                                    1/1     Running            0          26d
    kube-system         aws-node-xwkph                                                    1/1     Running            1          68d
    kube-system         cluster-autoscaler-5ddfc79fb6-8cxps                               1/1     Running            1          48d
    kube-system         coredns-6598bc95b5-d72qc                                          1/1     Running            0          77d
    kube-system         coredns-6598bc95b5-g4fjv                                          1/1     Running            0          77d
    kube-system         efs-provisioner-8667b475d8-z99n5                                  1/1     Running            0          77d
    kube-system         guard-685fd745c4-h8zx5                                            1/1     Running            104        47d
    kube-system         heapster-heapster-68c9756598-8q6g2                                2/2     Running            0          45d
    kube-system         k8s-spot-termination-handler-dpbvk                                1/1     Running            0          45d
    kube-system         k8s-spot-termination-handler-gnbfn                                1/1     Running            0          26d
    kube-system         k8s-spot-termination-handler-n7qvk                                1/1     Running            0          68d
    kube-system         k8s-spot-termination-handler-rbmgf                                1/1     Running            0          68d
    kube-system         kube-proxy-hlfff                                                  1/1     Running            0          68d
    kube-system         kube-proxy-jk7vn                                                  1/1     Running            0          77d
    kube-system         kube-proxy-m7m9x                                                  1/1     Running            0          26d
    kube-system         kube-proxy-mf58b                                                  1/1     Running            0          45d
    kube-system         kube-state-metrics-5f958c6d59-qs5zg                               1/1     Running            0          38d
    kube-system         kubernetes-dashboard-75576f5d59-4p6cp                             1/1     Running            0          76d
    kube-system         metrics-server-64cdf474f7-8vs4l                                   1/1     Running            0          76d
    kube-system         nginx-ingress-controller-7899b5b5dd-c4s4v                         1/1     Running            0          76d
    kube-system         tiller-deploy-54fc6d9ccc-zr9zh                                    1/1     Running            0          59d
    monitor             fluentd-elasticsearch-7kpqd                                       1/1     Running            0          26d
    monitor             fluentd-elasticsearch-gdjxz                                       1/1     Running            0          26d
    monitor             fluentd-elasticsearch-lzz8w                                       1/1     Running            0          26d
    monitor             fluentd-elasticsearch-t76gs                                       1/1     Running            0          26d
    monitor             grafana-9474c8f77-hb8cq                                           1/1     Running            0          48d
    monitor             jaeger-agent-625tn                                                1/1     Running            0          40d
    monitor             jaeger-agent-6vwxp                                                1/1     Running            0          40d
    monitor             jaeger-agent-788ck                                                1/1     Running            0          26d
    monitor             jaeger-agent-gfqdv                                                1/1     Running            0          40d
    monitor             jaeger-collector-674f44d74b-t9wqm                                 1/1     Running            1          40d
    monitor             jaeger-query-fb8d69547-zlk94                                      1/1     Running            0          40d
    monitor             prometheus-adapter-669d68857-wtzl6                                1/1     Running            0          48d
    monitor             prometheus-alertmanager-646b64b9f7-rh5tf                          2/2     Running            0          48d
    monitor             prometheus-node-exporter-55n4j                                    1/1     Running            0          48d
    monitor             prometheus-node-exporter-6cd5j                                    1/1     Running            0          45d
    monitor             prometheus-node-exporter-gdggp                                    1/1     Running            0          48d
    monitor             prometheus-node-exporter-jzzcc                                    1/1     Running            0          26d
    monitor             prometheus-pushgateway-76858f996-bs8d2                            1/1     Running            0          48d
    monitor             prometheus-server-697f6dc766-jzf25                                2/2     Running            0          48d
    newalertnow-dev     newalertnow-incident-66f6599db4-btkf7                             0/1     CrashLoopBackOff   1233       4d8h
    newalertnow-dev     newalertnow-incident-66f6599db4-d7grs                             0/1     CrashLoopBackOff   1411       5d
    opsbot-dev          opsbot-front-6756584485-mnfq7                                     1/1     Running            0          132m
    opsbot-dev          opsbot-fulfill-5d687b54f6-8f8bv                                   1/1     Running            0          4h13m
    opsbot-dev          opsbot-fulfill-5d687b54f6-kccdk                                   1/1     Running            0          4h13m
    opsbot-dev          opsbot-proxy-776ccd686-ngddp                                      1/1     Running            0          4h7m
    opsbot-stage        opsbot-front-5488dcdb74-m8l2h                                     1/1     Running            0          4h18m
    opsbot-stage        opsbot-fulfill-57744c78cc-fjs4h                                   1/1     Running            0          3h46m
    opsbot-stage        opsbot-fulfill-57744c78cc-vx5ct                                   1/1     Running            0          3h47m
    opsbot-stage        opsbot-proxy-7dc445974b-95n57                                     1/1     Running            0          4d8h
    resale-dev          resale-admin-5f4f48fdb8-d4h4p                                     1/1     Running            0          3h49m
    resale-dev          resale-client-5c59cc5856-dtp98                                    1/1     Running            0          141m
    resale-stage        resale-admin-64d847cf9-2jdzm                                      1/1     Running            0          4h14m
    resale-stage        resale-client-6b48d75975-99z75                                    1/1     Running            0          3d
    sample-dev          sample-node-75d86c68d4-cvlkj                                      1/1     Running            0          4d3h
    sample-dev          sample-node-redis-569c47b7db-qjcsr                                1/1     Running            0          4d8h
    sample-dev          sample-spring-5f84569f85-65bwf                                    1/1     Running            6          4d3h
    sample-dev          sample-tomcat-6f677f5c77-jbhqb                                    1/1     Running            0          4h36m
    sample-dev          sample-webpack-59968cc6f4-dgxk8                                   1/1     Running            0          4h36m
    sample-stage        sample-node-5d76849677-lk5fq                                      1/1     Running            0          4d3h
    sample-stage        sample-node-redis-d94b69b56-xmmnl                                 1/1     Running            0          4h36m

    '''

    '''
    [ec2-user@seoul-dev-okc1-bastion test]$ k describe pvc -n monitor grafana
    Name:          grafana
    Namespace:     monitor
    StorageClass:  efs
    Status:        Bound
    Volume:        pvc-350192ea-456d-11e9-bb58-0a3c8e8c39c4
    Labels:        app=grafana
                   release=grafana
    Annotations:   pv.kubernetes.io/bind-completed: yes
                   pv.kubernetes.io/bound-by-controller: yes
                   volume.beta.kubernetes.io/storage-provisioner: seoul-dev-okc1-eks/efs
    Finalizers:    [kubernetes.io/pvc-protection]
    Capacity:      5Gi
    Access Modes:  RWO
    Events:        <none>
    Mounted By:    grafana-9474c8f77-hb8cq
    '''