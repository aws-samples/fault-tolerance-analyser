# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class VPCEAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'vpce')

    def get_findings(self):
        session = self.get_aws_session()
        ec2 = session.client("ec2", region_name=self.region)

        for vpce in utils.invoke_aws_api_full_list(ec2.describe_vpc_endpoints, "VpcEndpoints", Filters = [ {'Name':'vpc-endpoint-type', 'Values' : ['Interface']} ]):
            subnet_ids = vpce["SubnetIds"]

            finding_rec = self.get_finding_rec_from_response(vpce)

            if len(subnet_ids) > 1:
                finding_rec['potential_single_az_issue'] = False
                finding_rec['message'] = f"VPCE: {vpce['VpcEndpointId']} has multiple subnets: {subnet_ids}"
            else:
                finding_rec['potential_single_az_issue'] = True
                finding_rec['message'] = f"VPCE: {vpce['VpcEndpointId']} has a single subnet: {subnet_ids}"

            self.findings.append(finding_rec)

    def get_finding_rec_from_response(self, vpce):

        finding_rec = self.get_finding_rec_with_common_fields()

        finding_rec['resource_id'] = vpce['VpcEndpointId']
        finding_rec['resource_name'] = ''
        for tag in vpce['Tags']:
            if tag['Key'] == 'Name':
                finding_rec['resource_name'] = tag['Value']
        finding_rec['resource_arn'] = vpce['ServiceName']
        return finding_rec
