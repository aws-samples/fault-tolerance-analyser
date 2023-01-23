# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class DocDBAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'docdb')

    def get_findings(self):
        session = self.get_aws_session()
        docdb = session.client("docdb", region_name=self.region)

        for db_cluster in utils.invoke_aws_api_full_list(docdb.describe_db_clusters, "DBClusters"):
            if db_cluster["Engine"] == "docdb": #Neptune clusters could also be listed. Hence we need to look only for docdb
                finding_rec = self.get_finding_rec_from_response(db_cluster)
                if db_cluster["MultiAZ"]:
                    finding_rec['potential_single_az_risk'] = False
                    finding_rec['message'] = "DocDB Cluster: {db_cluster['DBClusterIdentifier']} is in multiple AZs"
                else:
                    finding_rec['potential_single_az_risk'] = True
                    finding_rec['message'] = f"DocDB Cluster: {db_cluster['DBClusterIdentifier']} is in a single AZ"
                self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, db_cluster):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = db_cluster['DbClusterResourceId']
        finding_rec['resource_name'] = db_cluster['DBClusterIdentifier']
        finding_rec['resource_arn'] = db_cluster['DBClusterArn']
        return finding_rec 
