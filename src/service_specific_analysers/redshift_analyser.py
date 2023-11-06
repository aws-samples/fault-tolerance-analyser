# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import utils
from service_analyser import ServiceAnalyser

class RedshiftAnalyser(ServiceAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'redshift')

    def get_findings(self):
        session = self.get_aws_session()
        redshift = session.client("redshift", region_name=self.region)

        for cluster in utils.invoke_aws_api_full_list(redshift.describe_clusters, "Clusters"):
            finding_rec = self.get_finding_rec_from_response(cluster)
            if cluster["MultiAZ"] == "Enabled":
                finding_rec['potential_issue'] = False
                finding_rec['message'] = f"Redshift Cluster: {cluster['ClusterIdentifier']} is in multiple AZs"
            else:
                finding_rec['potential_issue'] = True
                finding_rec['message'] = f"Redshift Cluster: {cluster['ClusterIdentifier']} is in a single AZ"
            self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, cluster):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = cluster['ClusterIdentifier']
        finding_rec['resource_name'] = cluster['ClusterIdentifier']
        finding_rec['resource_arn'] = f"arn:aws:redshift:{self.region}:{self.account_analyser.account_id}:cluster-name/{cluster['ClusterIdentifier']}"
        return finding_rec 
