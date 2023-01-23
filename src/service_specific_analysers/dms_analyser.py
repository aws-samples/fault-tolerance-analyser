# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

class DMSAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        self.dms_instances = {}
        super().__init__(account_analyser, region, 'dms')

    def get_findings(self):

        session = self.get_aws_session()

        dms = session.client("dms", region_name=self.region)

        #Go through the instances, and gather findings.
        for repl_inst in utils.invoke_aws_api_full_list(dms.describe_replication_instances, "ReplicationInstances"):
            self.dms_instances[repl_inst["ReplicationInstanceArn"]] = {
                                        "MultiAZ":repl_inst["MultiAZ"],
                                        "ReplicationInstanceIdentifier":repl_inst["ReplicationInstanceIdentifier"],
                                        "AZs": [
                                                repl_inst["AvailabilityZone"],
                                                repl_inst["SecondaryAvailabilityZone"] if "SecondaryAvailabilityZone" in repl_inst else None
                                                ]
            }
            finding_rec = self.get_finding_rec_from_inst_response(repl_inst)

            if repl_inst["MultiAZ"]:
                finding_rec['potential_single_az_risk'] = False
                finding_rec['message'] = f"DMS Replication Instance: {repl_inst['ReplicationInstanceIdentifier']} with ARN {repl_inst['ReplicationInstanceArn']} in an instance with multiple AZs"
            else:
                finding_rec['potential_single_az_risk'] = True
                finding_rec['message'] = f"DMS Replication Instance: {repl_inst['ReplicationInstanceIdentifier']} with ARN {repl_inst['ReplicationInstanceArn']} is on an instance in a single AZ"
            self.findings.append(finding_rec)

        #Go through the tasks and gather findings.
        for repl_task in utils.invoke_aws_api_full_list(dms.describe_replication_tasks, "ReplicationTasks"):

            finding_rec = self.get_finding_rec_from_task_response(repl_task)

            dms_instance_arn = repl_task["ReplicationInstanceArn"]
            if self.dms_instances[dms_instance_arn]["MultiAZ"]:
                finding_rec['potential_single_az_risk'] = False
                finding_rec['message'] = f"DMS Replication Task: {repl_task['ReplicationTaskIdentifier']} with ARN {repl_task['ReplicationTaskArn']} in on the replication instance {self.dms_instances[dms_instance_arn]['ReplicationInstanceIdentifier']} which is configured with multiple AZs: {self.dms_instances[dms_instance_arn]['AZs']}"
            else:
                finding_rec['potential_single_az_risk'] = True
                finding_rec['message'] = f"DMS Replication Task: {repl_task['ReplicationTaskIdentifier']} with ARN {repl_task['ReplicationTaskArn']} is on the replication instance  {self.dms_instances[dms_instance_arn]['ReplicationInstanceIdentifier']} which is configured only in a single AZ {self.dms_instances[dms_instance_arn]['AZs'][0]}."
            
            self.findings.append(finding_rec)

    def get_finding_rec_from_inst_response(self, repl_inst):
        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = repl_inst['ReplicationInstanceIdentifier']
        finding_rec['resource_name'] = ''
        finding_rec['resource_arn'] = repl_inst['ReplicationInstanceArn']

        return finding_rec 

    def get_finding_rec_from_task_response(self, repl_task):
        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = repl_task['ReplicationTaskIdentifier']
        finding_rec['resource_name'] = ''
        finding_rec['resource_arn'] = repl_task['ReplicationTaskArn']

        return finding_rec 
