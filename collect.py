#!/usr/bin/python
import os
import sys
import subprocess
import timeit

def humanbytes(B):
   'Return the given bytes as a human friendly KB, MB, GB, or TB string'
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

if __name__ == "__main__":
    ##### Count filesystem size for du / df 
    ##### It failed because prometheus server can't use '/bin/bash' or '/bin/sh', so it du / df command didn't work.
    
    start = timeit.default_timer()
    get_namespaces = []
    get_namespace = subprocess.check_output("kubectl get pvc --all-namespaces | awk '{print $1}'", shell=True)
    get_pvc_name = subprocess.check_output("kubectl get pvc --all-namespaces | awk '{print $2}'", shell=True)
    get_pvc_id = subprocess.check_output("kubectl get pvc --all-namespaces | awk '{print $4}'", shell=True)


    get_namespaces = get_namespace.decode("utf-8").split()
    get_pvc_names = get_pvc_name.decode("utf-8").split()
    get_pvc_ids = get_pvc_id.decode("utf-8").split()


    if not get_namespaces:
        print("It didn't find namespaces / you should check kubernetes cluster")
    else:
        get_namespaces.pop(0)
        get_pvc_names.pop(0)
        get_pvc_ids.pop(0)
        
        print(get_namespaces)

        get_efs_provisioner_name = subprocess.check_output("kubectl get pod -n kube-system | grep efs | awk '{print $1}'", shell=True)
        get_efs_provisioner_name = get_efs_provisioner_name.decode("utf-8").replace('\n','')
        
        
        for val in range(len(get_namespaces)):
            find_dir_cmd = "kubectl exec -it " + get_efs_provisioner_name + " -n kube-system -- ls -al /persistentvolumes | awk '{print $9}' | grep " + get_pvc_names[val] + "-" + get_pvc_ids[val]
            try:
                find_dir = subprocess.check_output(find_dir_cmd, shell=True)
                find_dir = find_dir.decode("utf-8")
            except subprocess.CalledProcessError as ex:
                o = ex.output
                returncode = ex.returncode
                if returncode != 1:
                    raise

            if find_dir:
                ## pod name
                pod_name_cmd = "kubectl describe pvc -n " + get_namespaces[val] + " " + get_pvc_names[val] + " | grep Mounted | awk '{print $3}'"
                pod_name = subprocess.check_output(pod_name_cmd, shell=True)
                pod_name = pod_name.decode("utf-8")

                if 'none' not in pod_name.replace('\n',''):
                    ## calculate all size
                    ## it has a bug --> du caculate too late so tty timeout and it doesn't calculate 
                    # mount_size_cmd = "kubectl exec -it " + get_efs_provisioner_name + " -n kube-system -- du -c -hs /persistentvolumes/" + get_pvc_names[val] + "-" + get_pvc_ids[val] + " | awk '{print $1}'"
                    # m_size = subprocess.check_output(mount_size_cmd, shell=True)
                    # m_size = m_size.split().pop(0)
                    #mount_size.append(m_size)
                    #print(mount_size)

                    ## find list
                    print("pvc name : "+get_pvc_names[val])
                    find_file_list_cmd = "kubectl exec -it " +get_efs_provisioner_name + " -n kube-system -- ls -al /persistentvolumes/" + get_pvc_names[val] + "-" + get_pvc_ids[val] + " | awk '{print $9}' | sed -r \"s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[mGK]//g\""
                    find_file_list = subprocess.check_output(find_file_list_cmd, shell=True)
                    find_file_list = find_file_list.decode("utf-8").split()
                    find_file_list.remove('.')
                    find_file_list.remove('..')
                    # print(find_file_list)

                    if len(find_file_list) != 0:
                        mount_size=[]
                        for _file in find_file_list:
                            m_size_cmd = "kubectl exec -it " + get_efs_provisioner_name + " -n kube-system -- du -ks /persistentvolumes/" + get_pvc_names[val] + "-" + get_pvc_ids[val] + "/" + _file + " | awk '{print $1}'"
                            m_size = subprocess.check_output(m_size_cmd, shell=True)
                            m_size=m_size.decode("utf-8").split()
                            # print(''.join(m_size))
                            mount_size.append(''.join(m_size))
                        mount_size = list(map(int, mount_size))
                        sum_size = sum(mount_size)
                        # if sum_size < 1024:
                        #     print(get_namespaces[val] + " " + pod_name.replace('\n','') + " " + str(sum_size)+ "Kb")
                        # elif sum_size < 1048576:
                        #     sum_size=round(1.00*sum_size/1024.00)
                        #     print(get_namespaces[val] + " " + pod_name.replace('\n','') + " " + str(sum_size)+ "Mb")
                        # else:
                        #     sum_size=round(1.00*sum_size/1024.00)
                        #     sum_size=round(1.00*sum_size/1024.00)
                        sum_size = humanbytes(sum_size*1024)
                        print("EFS PVC Monitor >> " + " namespace = " + get_namespaces[val] + "/ pod name = " + pod_name.replace('\n','') + "/ PVC size =  " + str(sum_size))
                    else:
                        print("EFS PVC Monitor >> " + " namespace = " + get_namespaces[val] + "/ pod name = " + pod_name.replace('\n','') +" / PVC size =  " + "4KB")
                    #print(pod_name_cmd)
                    #print('pod name : ' + pod_name.replace('\n',''))
                
                    ## namespace / pod name / size
                
    stop = timeit.default_timer()
    laptime=stop-start
    print('laptime = ' + str(laptime))
    
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



    # result = subprocess.check_output("kubectl get pv --all-namespaces -o json | jq '.items[].status.phase'", shell=True)
    # result=result.replace('"','')
    # a=0
    # result_list=result.split("\n")
    # namespace_list=[]
    # for s in result_list:
    #     ## check if pv is "Bound"
    #     if "Bound" == s:
    #         a=a+1
    #         a=str(a)

    #         ## find name / namespace for pv which is "Bound"
    #         name_cmd = "kubectl get pv --all-namespaces -o json | jq '.items[" + a + "].spec.claimRef.name'"
    #         name = subprocess.check_output(name_cmd, shell=True).rstrip()
    #         namespace_cmd = "kubectl get pv --all-namespaces -o json | jq '.items[" + a + "].spec.claimRef.namespace'"
    #         namespace = subprocess.check_output(namespace_cmd, shell=True)
    #         a=int(a)
    #         # print(name + " " + namespace)
    #         namespace=''.join(namespace.rstrip())
    #         namespace_list.append(namespace)

    # ## remove duplicate values
    # mount_pod_list=[]
    # mount_path_list=[]
    # namespace_list = list(set(namespace_list))
    # for val in namespace_list:
    #     ## find pod mounted
    #     print("val = "+val)
    #     mount_pod_cmd = "kubectl describe pvc -n " + val + " | grep Mounted | awk '{print $3}'"
    #     mount_pod = subprocess.check_output(mount_pod_cmd, shell=True)
    #     mount_pod=mount_pod.split("\n")

    #     for m_path in mount_pod:
    #         ## find mountPath in pod
    #         if m_path != "<none>" and m_path:
    #             print("path = "+m_path)
    #             mount_path_cmd = "kubectl get pod -n " + val + " " + m_path + " -o json | jq '.spec.containers[].volumeMounts[].mountPath'"
    #             mount_path=subprocess.check_output(mount_path_cmd, shell=True)
    #             print(mount_path+"\n")
                
    #             ## append list in list
    #             for xx in mount_path.split("\n"):
    #                 if "secrets" not in xx and xx and "yaml" not in xx and "ini" not in xx and "toml" not in xx and "config" not in xx:
    #                     print(xx)
    #                     mount_size_cmd = "kubectl exec -it -n " + val + " " + m_path + " -- du -c -hs " + xx.replace('"','')
    #                     mount_size = subprocess.check_output(mount_size_cmd, shell=True)
    #                     print(mount_size_cmd)
    #                     print(mount_size)
    #                     # mount_path_temp_list=xx.rstrip()
    #                     # mount_path_list.append(mount_path_temp_list)
    #                     print("================================================")
    #         else:
    #             continue

    # print(mount_path_list)
