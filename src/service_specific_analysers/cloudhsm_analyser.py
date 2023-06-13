# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class CloudHSMAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'efs')

    def get_findings(self):
        session = self.get_aws_session()
        efs = session.client("cloudhsmv2", region_name=self.region)

        for cluster in utils.invoke_aws_api_full_list(efs.describe_clusters, "Clusters"):

            finding_rec = self.get_finding_rec_from_response(cluster)

            if len(cluster["Hsms"]) == 0:
                finding_rec['potential_single_az_issue'] = False
                finding_rec['message'] = f"CloudHSM: Cloud HSM cluster {cluster['ClusterId']} has only no hsms."
            elif len(cluster["Hsms"]) == 1:
                finding_rec['potential_single_az_issue'] = True
                finding_rec['message'] = f"CloudHSM: Cloud HSM cluster {cluster['ClusterId']} has only 1 hsm in a single AZ {cluster['Hsms'][0]['AvailabilityZone']}."
            elif len(cluster["Hsms"]) > 1:
                azs = set()
                for hsm in cluster['Hsms']:
                    azs.add(hsm['AvailabilityZone'])
                if len(azs) == 1:
                    finding_rec['potential_single_az_issue'] = True
                    finding_rec['message'] = f"CloudHSM: Cloud HSM cluster {cluster['ClusterId']} has {len(cluster['Hsms'])} hsms but they are all in the AZ {azs.pop()}"
                else: #len(azs) > 1
                    finding_rec['potential_single_az_issue'] = False
                    finding_rec['message'] = f"CloudHSM: Cloud HSM cluster {cluster['ClusterId']} has {len(cluster['Hsms'])} hsms and they are spread across multiple AZs: {list(azs)}"
            self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, cluster):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = cluster['ClusterId']
        finding_rec['resource_name'] = cluster['ClusterId']
        finding_rec['resource_arn'] = f"arn:aws:cloudhsm:{self.region}:{self.account_analyser.account_id}:cluster/{cluster['ClusterId']}"
        return finding_rec 
