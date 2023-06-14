# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_analyser import ServiceAnalyser

class FSXAnalyser(ServiceAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'fsx')

    def get_findings(self):

        session = self.get_aws_session()
        fsx = session.client("fsx", region_name=self.region)

        for fs in utils.invoke_aws_api_full_list(fsx.describe_file_systems, "FileSystems"):
            if fs['FileSystemType'] == "WINDOWS": #We look only at Windows File systems
                finding_rec = self.get_finding_rec_from_response(fs)
                if len(fs["SubnetIds"]) == 1:
                    finding_rec['potential_issue'] = True
                    finding_rec['message'] = f"FSX: Windows File system {fs['FileSystemId']} with ARN {fs['ResourceARN'] } is a single AZ file system. Please check."
                else:
                    finding_rec['potential_issue'] = False
                    finding_rec['message'] = f"FSX: Windows File system {fs['FileSystemId']} with ARN {fs['ResourceARN'] } is a multi AZ file system"
                self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, fs):
        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = fs['FileSystemId']
        finding_rec['resource_name'] = ''
        for tag in fs['Tags']:
            if tag['Key'] == 'Name':
                finding_rec['resource_name'] = tag['Value']
        finding_rec['resource_arn'] = fs['ResourceARN']

        return finding_rec 
