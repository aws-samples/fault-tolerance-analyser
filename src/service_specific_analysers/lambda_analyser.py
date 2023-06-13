# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class LambdaAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'lambda')

    def get_findings(self):
        session = self.get_aws_session()
        aws_lambda = session.client("lambda", region_name=self.region)

        for lambda_func in utils.invoke_aws_api_full_list(aws_lambda.list_functions, "Functions"):

            if "VpcConfig" not in lambda_func.keys(): #Ignore if there is no VpcConfig in the function
                continue

            if lambda_func["VpcConfig"]["VpcId"]: #If it is populated only then is it VPC Enabld. If not, this check can be ignored.
                finding_rec = self.get_finding_rec_from_response(lambda_func)
                if len(lambda_func["VpcConfig"]["SubnetIds"]) == 1:
                    finding_rec['potential_single_az_issue'] = True
                    finding_rec['message'] = f"Lambda: VPC Enabled Lambda function {lambda_func['FunctionName']} is configured to run in only one subnet."
                else:
                    finding_rec['potential_single_az_issue'] = False
                    finding_rec['message'] = f"Lambda: VPC Enabled Lambda Function {lambda_func['FunctionName']} is configured to run in more than one subnet"
                self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, lambda_func):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = ''
        finding_rec['resource_name'] = lambda_func['FunctionName']
        finding_rec['resource_arn'] = lambda_func['FunctionArn']
        return finding_rec 
