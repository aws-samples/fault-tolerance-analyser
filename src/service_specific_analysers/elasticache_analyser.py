# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class ElasticacheAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'elasticache')

    def get_findings(self):
        self.session = self.get_aws_session()
        self.elasticache = self.session.client("elasticache", region_name=self.region)
        self.get_memcache_single_node_redis_findings()
        self.get_redis_replication_group_findings()

    def get_memcache_single_node_redis_findings(self):

        #Get memcached and single node Redis clusters        
        for cluster in utils.invoke_aws_api_full_list(self.elasticache.describe_cache_clusters, "CacheClusters", ShowCacheClustersNotInReplicationGroups = True):
            finding_rec = self.get_output_from_memcache_single_node_redis_response(cluster)
            finding_rec['potential_single_az_risk'] = True
            if cluster['Engine'] == 'redis': #Single node redis cluster
                finding_rec['message'] = "Elasticache-Redis cluster: {cluster['CacheClusterId']} is a single Node Elasticache-Redis cluster"
            else: #Memcached cluster
                finding_rec['message'] = "Elasticache-Memcached cluster: {cluster['CacheClusterId']} is a single AZ risk even if there are multiple nodes in multiple AZs as the data is not replicated between nodes."
            self.findings.append(finding_rec)

    def get_output_from_memcache_single_node_redis_response(self, cluster):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = cluster['CacheClusterId']
        finding_rec['resource_name'] = cluster['CacheClusterId']
        finding_rec['resource_arn'] = cluster['ARN']
        finding_rec['engine'] = cluster['Engine']
        return finding_rec 

    def get_redis_replication_group_findings(self):
        #Get Redis replication group clusters
        
        for repl_group in utils.invoke_aws_api_full_list(self.elasticache.describe_replication_groups, "ReplicationGroups"):
            finding_rec = self.get_output_from_redis_replication_group_response(repl_group)
            if len(repl_group["NodeGroups"]) == 0 : #Cluster Mode disabled. And no node groups or shards. So the data is not replicated across nodes and so this is not single AZ failure resilient
                finding_rec['potential_single_az_risk'] = True
                finding_rec['message'] = f"Elasticache-Redis Replication Group: {repl_group['ReplicationGroupId']}: Cluster Mode disabled and no node groups configured"
            elif len(repl_group["NodeGroups"]) == 1 : #Cluster Mode disabled. One node group/shard
                if repl_group["AutomaticFailover"] == "disabled":
                    finding_rec['potential_single_az_risk'] = True
                    finding_rec['message'] = f"Elasticache-Redis Replication Group: {repl_group['ReplicationGroupId']}: Cluster Mode disabled, 1 Node group configured but Auto Failover is disabled"
                elif repl_group["MultiAZ"] == "disabled": #Auto failover enabled, but multi AZ disabled
                    node_group = repl_group["NodeGroups"][0]
                    azs = set()
                    for node in node_group["NodeGroupMembers"]:
                        azs.add(node["PreferredAvailabilityZone"])
                    if len(azs) == 1: #All nodes belong to the same AZ
                        finding_rec['potential_single_az_risk'] = True
                        finding_rec['message'] = f"Elasticache-Redis Replication Group: {repl_group['ReplicationGroupId']}: Cluster Mode disabled and Auto Failover is enabled, but all nodes are in the same AZ {azs}"
                    else:
                        finding_rec['potential_single_az_risk'] = False
                        finding_rec['message'] = f"Elasticache-Redis Replication Group: {repl_group['ReplicationGroupId']}: Cluster Mode disabled, and Auto Failover is enabled. but the nodes are not in multiple AZs {azs}"
                else: # Auto failover enabled and multi AZ enabled. So this is ok.
                    finding_rec['potential_single_az_risk'] = False
                    finding_rec['message'] = f"Elasticache-Redis Replication Group: {repl_group['ReplicationGroupId']}: Cluster Mode disabled, but Auto Failover and Multi AZ enabled"
            # At this point len(repl_group["NodeGroups"]) > 1 which implies cluster mode is enabled.
            # This means that Automatic failover is enabled by force.
            # The customer does not have an option to disable it. So that need not be checked.
            # Just make sure all nodes of a given shard are not in the same AZ and that each shard has a replication node.
            elif repl_group["MultiAZ"] == "disabled":
                #Check to see if any replicas are missing in any node groups, or if any node groups have all the nodes in the same AZ.
                node_groups = repl_group["NodeGroups"]
                risk_found = False
                for node_group in node_groups:
                    if len(node_group["NodeGroupMembers"]) == 1:
                        finding_rec['potential_single_az_risk'] = True
                        finding_rec['message'] = f"Elasticache-Redis Replication Group: {repl_group['ReplicationGroupId']}: Cluster Mode enabled, but no replicas in shard {node_group['NodeGroupId']}"
                        risk_found = True
                        break
                    else:
                        azs = set()
                        for node in node_group["NodeGroupMembers"]:
                            azs.add(node["PreferredAvailabilityZone"])
                        if len(azs) == 1: #All nodes belong to the same AZ
                            finding_rec['potential_single_az_risk'] = True
                            finding_rec['message'] = f"Elasticache-Redis Replication Group: {repl_group['ReplicationGroupId']}: Cluster Mode enabled, but all nodes in shard {node_group['NodeGroupId']} are in the same AZ {azs}"
                            risk_found = True
                            break
                if not risk_found: #All Node groups have been ok
                    finding_rec['potential_single_az_risk'] = False
                    finding_rec['message'] = f"Elasticache-Redis Replication Group: {repl_group['ReplicationGroupId']}: Cluster Mode enabled, all nodegroups have replicas and none of those node groups have all the nodes in the same AZ."
            else:
                finding_rec['potential_single_az_risk'] = False
                finding_rec['message'] = f"Elasticache-Redis Replication Group: {repl_group['ReplicationGroupId']}: Cluster Mode enabled, and Multi AZ is enabled."
            self.findings.append(finding_rec)

    def get_output_from_redis_replication_group_response(self, repl_group):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = repl_group['ReplicationGroupId']
        finding_rec['resource_name'] = repl_group['ReplicationGroupId']
        finding_rec['resource_arn'] = repl_group['ARN']
        finding_rec['engine'] = 'Redis' #This is the only possibility for replicationg groups.
        return finding_rec 
