# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_analyser import ServiceAnalyser

class MemoryDBAnalyser(ServiceAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'memorydb')

    def get_findings(self):
        self.session = self.get_aws_session()
        self.memorydb = self.session.client("memorydb", region_name=self.region)
        self.get_memorydb_findings()

    def get_memorydb_findings(self):

        for cluster in utils.invoke_aws_api_full_list(self.memorydb.describe_clusters, "Clusters", ShowShardDetails = True):
            finding_rec = self.get_finding_rec_from_response(cluster)
            issue_found = False
            for shard in cluster["Shards"]:
                if len(shard["Nodes"]) == 1:
                    finding_rec['potential_issue'] = True
                    finding_rec['message'] = f"Memory DB Cluster: Shard {shard['Name']} in cluster {cluster['Name']} does not have any replicas"
                    issue_found = True
                    break            

            if not issue_found:
                finding_rec['potential_issue'] = False
                finding_rec['message'] = f"Memory DB Cluster: All shards in cluster {cluster['Name']} have replicas"
            self.findings.append(finding_rec)

    def get_finding_rec_from_response(self, cluster):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = ''
        finding_rec['resource_name'] = cluster['Name']
        finding_rec['resource_arn'] = cluster['ARN']
        return finding_rec 
