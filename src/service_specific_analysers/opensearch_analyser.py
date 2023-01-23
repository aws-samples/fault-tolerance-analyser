# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class OpensearchAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'opensearch')

    def get_findings(self):

        session = self.get_aws_session()
        opensearch = session.client("opensearch", region_name=self.region)
        domain_name_batches = [] #List of batches
        batch_size = 5
        batch_counter = 0
        domain_counter = 0

        #Get the list of domain names and batch them in batch_size
        for domain_name in utils.invoke_aws_api_full_list(opensearch.list_domain_names, "DomainNames"):
            if ((domain_counter % batch_size) == 0):
                domain_name_batches.append([])
            domain_counter = domain_counter + 1
            domain_name_batches[len(domain_name_batches)-1].append(domain_name['DomainName'])

        #Validate the domain names in batches as the validate_opensearch_domains API can get information about multiple domains in one API call.
        for domain_name_batch in domain_name_batches:
            self.validate_opensearch_domains(opensearch, domain_name_batch)

    def validate_opensearch_domains(self, opensearch, domain_names):

        for domain in utils.invoke_aws_api_full_list(opensearch.describe_domains, "DomainStatusList", DomainNames = domain_names):
            finding_rec = self.get_finding_rec_from_response(domain)
            if len(domain["VPCOptions"]["AvailabilityZones"]) > 1:
                finding_rec['potential_single_az_risk'] = False
                finding_rec['message'] = f"Opensearch domain: Domain {domain['DomainName']} with ARN {domain['ARN'] } is multi AZ enabled."
            else:
                finding_rec['potential_single_az_risk'] = True
                finding_rec['message'] = f"Opensearch domain: Domain {domain['DomainName']} with ARN {domain['ARN'] } is only in a single AZ."
            self.findings.append(finding_rec)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, domain):
        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['service'] = 'opensearch'
        finding_rec['region'] = self.region
        finding_rec['resource_id'] = domain['DomainId']
        finding_rec['resource_name'] = domain['DomainName']
        finding_rec['resource_arn'] = domain['ARN']
        return finding_rec 
