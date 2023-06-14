# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_analyser import ServiceAnalyser

class GlobalAcceleratorAnalyser(ServiceAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'globalaccelerator')

    def get_findings(self):

        if self.region == "us-west-2":
            self.session = self.get_aws_session()
            self.aga = self.session.client("globalaccelerator", region_name=self.region)
            self.get_standard_accelerator_findings()
        else:
            logging.info(f"The service Global Accelerator operates only in us-west-2. Hence doing nothing for {self.region}")
            return #Nothing to do since Global Accelerator operates only in us-west-2

    def get_standard_accelerator_findings(self):
        for accelerator in utils.invoke_aws_api_full_list(self.aga.list_accelerators, "Accelerators", ):
            self.validate_standard_accelerator(accelerator)

    def validate_standard_accelerator(self, accelerator):
        finding_rec = self.get_finding_rec_from_response(accelerator)

        ec2_instance_ids = []
        target_regions = set()
        for listener in utils.invoke_aws_api_full_list(self.aga.list_listeners,
                                                "Listeners",
                                                AcceleratorArn = accelerator["AcceleratorArn"]):
            for endpoint_group in utils.invoke_aws_api_full_list(self.aga.list_endpoint_groups,
                                                "EndpointGroups",
                                                ListenerArn = listener["ListenerArn"]):
                target_regions.add(endpoint_group["EndpointGroupRegion"])
                if len(target_regions) > 1:
                    #If multiple regions are available then they are Multi-AZ. No need to proceed further
                    finding_rec['potential_issue'] = False
                    finding_rec['message'] = f"Global Accelerator: {accelerator['Name']} has target endpoints are in multiple regions"
                    fself.findings.append(finding_rec)
                for endpoint in endpoint_group["EndpointDescriptions"]:
                    if not endpoint["EndpointId"].startswith("i-"): #Not EC2 instance
                        logging.info(f"Global Accelerator {accelerator['Name']} has endpoints that are not EC2 instances. Hence ignored.")
                        return
                    else:
                        ec2_instance_ids.append(endpoint["EndpointId"])

        #We have now collected all EC2 instances from all listeners and endpoint groups. Check the Availability zone of these EC2 instances now.
        #So get all AZs to which these EC2 instances belong        
        azs = self.get_azs_of_ec2_instances(ec2_instance_ids, next(iter(target_regions))) #We can use next(iter(target_regions) as we are sure there will be only one region. If there are more than one, we would not have come this far.

        if (len(azs) > 1):
            finding_rec['potential_issue'] = False
            finding_rec['message'] = f"Global Accelerator: All target endpoints for the acceleator {accelerator['Name']} are EC2 instances and they are spread across more than one AZ {azs}"
        else:
            finding_rec['potential_issue'] = True
            finding_rec['message'] = f"Global Accelerator: All target endpoints for the acceleator {accelerator['Name']} are EC2 instances and they are all in a single AZ {azs}"

        self.findings.append(finding_rec)

    def get_azs_of_ec2_instances(self, ec2_instance_ids, region):
        #First break up the EC2 instances in batches
        ec2_instance_id_batches = [] #List of batches
        batch_size = 10
        ec2_instance_counter = 0

        #Get the list of domain names and batch them in batch_size
        for ec2_instance_id in ec2_instance_ids:
            if ((ec2_instance_counter % batch_size) == 0):
                ec2_instance_id_batches.append([])
            ec2_instance_counter = ec2_instance_counter + 1
            ec2_instance_id_batches[len(ec2_instance_id_batches)-1].append(ec2_instance_id)

        azs = set()
        ec2 = self.session.client("ec2", region_name = region)
        #For each batch, invoke ec2 describe-instances and get the availability zones
        for ec2_instance_id_batch in ec2_instance_id_batches:
            resp = ec2.describe_instances(InstanceIds = ec2_instance_id_batch)
            #print(resp)

            for ec2_instance in utils.invoke_aws_api_full_list(ec2.describe_instances,
                                                "Reservations",
                                                InstanceIds = ec2_instance_id_batch):
                azs.add(ec2_instance["Instances"][0]["Placement"]["AvailabilityZone"])

        return(azs)

    #Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_finding_rec_from_response(self, accelerator):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = accelerator['DnsName']
        finding_rec['resource_name'] = accelerator['Name']
        finding_rec['resource_arn'] = accelerator['AcceleratorArn']
        return finding_rec 
