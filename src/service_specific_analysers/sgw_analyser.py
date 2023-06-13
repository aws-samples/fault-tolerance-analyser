# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class SGWAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'sgw')

    def get_findings(self):

        session = self.get_aws_session()
        sgw = session.client("storagegateway", region_name=self.region)

        for gateway in utils.invoke_aws_api_full_list(sgw.list_gateways, "Gateways"):
            finding_rec = self.get_finding_rec_from_response(gateway)
            if (("Ec2InstanceRegion" in gateway.keys()) and (len(gateway["Ec2InstanceRegion"]))):
                finding_rec['potential_single_az_issue'] = True
                finding_rec['message'] = f"Storge Gateway: Gateway {gateway['GatewayName']} with ARN {gateway['GatewayARN']} in hosted on AWS. Please ensure this gateway is not used for critical workloads"
            else:
                finding_rec['potential_single_az_issue'] = False
                finding_rec['message'] = f"Storge Gateway: Gateway {gateway['GatewayName']} is not hosted on AWS"

            self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, gateway):

        finding_rec = self.get_finding_rec_with_common_fields()

        finding_rec['resource_id'] = gateway['GatewayId']
        finding_rec['resource_name'] = gateway['GatewayName']
        finding_rec['resource_arn'] = gateway['GatewayARN']

        return finding_rec
