# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class RDSAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'rds')

    def get_findings(self):
        self.session = self.get_aws_session()
        self.rds = self.session.client("rds", region_name=self.region)
        self.get_db_instance_findings()
        self.get_db_cluster_findings()
    
    def get_db_instance_findings(self):
        for db_instance in utils.invoke_aws_api_full_list(self.rds.describe_db_instances, "DBInstances"):
            if db_instance["Engine"] == "docdb": #Ignore any Document DB instances as they are covered separately.
                continue
            
            if "DBClusterIdentifier" in db_instance: #This DB instance is part of a cluster. So it will be handled as part of cluster analyser
                continue

            finding_rec = self.get_finding_rec_from_response_instance(db_instance)

            if db_instance["MultiAZ"]:
                finding_rec['potential_single_az_issue'] = False
                finding_rec['message'] = f"RDS Instance: {db_instance['DBInstanceIdentifier']} has MultiAZ enabled"
            else:
                finding_rec['potential_single_az_issue'] = True
                finding_rec['message'] = f"RDS Instance: {db_instance['DBInstanceIdentifier']} has MultiAZ disabled"
            self.findings.append(finding_rec)

    def get_db_cluster_findings(self):
        for db_cluster in utils.invoke_aws_api_full_list(self.rds.describe_db_clusters, "DBClusters"):
            if db_cluster["Engine"] in ["docdb","neptune"]: #Ignore any Document DB, Neptune clusters.
                continue
            
            finding_rec = self.get_finding_rec_from_response_cluster(db_cluster)

            if db_cluster["MultiAZ"]:
                finding_rec['potential_single_az_issue'] = False
                finding_rec['message'] = f"RDS Cluster: {db_cluster['DBClusterIdentifier']} has MultiAZ enabled"
            else:
                finding_rec['potential_single_az_issue'] = True
                finding_rec['message'] = f"RDS Cluster {db_cluster['DBClusterIdentifier']} has MultiAZ disabled"
            self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response_instance(self, db_instance):

        finding_rec = self.get_finding_rec_with_common_fields()

        finding_rec['resource_id'] = ''
        finding_rec['resource_name'] = db_instance['DBInstanceIdentifier']
        finding_rec['resource_arn'] = db_instance['DBInstanceArn']
        finding_rec['engine'] = db_instance["Engine"]
        return finding_rec 

    def get_finding_rec_from_response_cluster(self, db_cluster):

        finding_rec = self.get_finding_rec_with_common_fields()

        finding_rec['resource_id'] = ''
        finding_rec['resource_name'] = db_cluster['DBClusterIdentifier']
        finding_rec['resource_arn'] = db_cluster['DBClusterArn']
        finding_rec['engine'] = db_cluster["Engine"]
        return finding_rec 
