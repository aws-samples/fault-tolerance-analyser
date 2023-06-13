# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class EFSAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'efs')

    def get_findings(self):
        session = self.get_aws_session()
        efs = session.client("efs", region_name=self.region)

        for fs in utils.invoke_aws_api_full_list(efs.describe_file_systems, "FileSystems"):
            finding_rec = self.get_finding_rec_from_response(fs)
            if "AvailabilityZoneId" in fs: #Single AZ File system
                finding_rec['potential_single_az_issue'] = True
                finding_rec['message'] = f"EFS: File system {fs['FileSystemId']} with ARN {fs['FileSystemArn'] } is a single AZ file system."
            elif fs["NumberOfMountTargets"] <= 1: #Multi AZ file system but mount target only in a single AZ
                finding_rec['potential_single_az_issue'] = True
                finding_rec['message'] = f"EFS: File system {fs['FileSystemId']} with ARN {fs['FileSystemArn'] } is a multi AZ enabled file system but with only one mount target."
            else:
                finding_rec['potential_single_az_issue'] = False
                finding_rec['message'] = f"EFS: File system {fs['FileSystemId']} with ARN {fs['FileSystemArn'] } is a multi AZ enabled file system with more than one mount target"
            self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, fs):
        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = fs['FileSystemId']
        finding_rec['resource_name'] = ''
        for tag in fs['Tags']:
            if tag['Key'] == 'Name':
                finding_rec['resource_name'] = tag['Value']
        finding_rec['resource_arn'] = fs['FileSystemArn']

        return finding_rec 

