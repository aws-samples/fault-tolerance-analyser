# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class DAXAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'dax')

    def get_findings(self):
        session = self.get_aws_session()
        dax = session.client("dax", region_name=self.region)

        for cluster in utils.invoke_aws_api_full_list(dax.describe_clusters, "Clusters"):
            finding_rec = self.get_finding_rec_from_response(cluster)
            azs = {node['AvailabilityZone'] for node in cluster["Nodes"]}

            if len(azs) > 1:
                finding_rec['potential_single_az_issue'] = False
                finding_rec['message'] = f"Nodes in DAX Cluster {cluster['ClusterName']} are spread across more than 1 AZ {azs}"
            else:
                finding_rec['potential_single_az_issue'] = True
                finding_rec['message'] = f"All nodes in the DAX cluster  {cluster['ClusterName']} are in a single AZ {azs}"
            self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, cluster):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = ''
        finding_rec['resource_name'] = cluster['ClusterName']
        finding_rec['resource_arn'] = cluster['ClusterArn']
        return finding_rec 
