# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import threading
import csv
import time
import logging
import utils
import boto3
import botocore
import datetime
import utils
import os

from service_specific_analysers.vpce_analyser import VPCEAnalyser
from service_specific_analysers.docdb_analyser import DocDBAnalyser
from service_specific_analysers.dms_analyser import DMSAnalyser
from service_specific_analysers.sgw_analyser import SGWAnalyser
from service_specific_analysers.efs_analyser import EFSAnalyser
from service_specific_analysers.opensearch_analyser import OpensearchAnalyser
from service_specific_analysers.fsx_analyser import FSXAnalyser
from service_specific_analysers.lambda_analyser import LambdaAnalyser
from service_specific_analysers.elasticache_analyser import ElasticacheAnalyser
from service_specific_analysers.dax_analyser import DAXAnalyser
from service_specific_analysers.globalaccelerator_analyser import GlobalAcceleratorAnalyser
from service_specific_analysers.rds_analyser import RDSAnalyser
from service_specific_analysers.memorydb_analyser import MemoryDBAnalyser
from service_specific_analysers.dx_analyser import DXAnalyser

from collections import namedtuple

class AccountResiliencyAnalyser():

    analyser_classes = {}
    analyser_classes['vpce'] = VPCEAnalyser
    analyser_classes['docdb'] = DocDBAnalyser
    analyser_classes['dms'] = DMSAnalyser
    analyser_classes['sgw'] = SGWAnalyser
    analyser_classes['efs'] = EFSAnalyser
    analyser_classes['opensearch'] = OpensearchAnalyser
    analyser_classes['fsx'] = FSXAnalyser
    analyser_classes['lambda'] = LambdaAnalyser
    analyser_classes['elasticache'] = ElasticacheAnalyser
    analyser_classes['dax'] = DAXAnalyser
    analyser_classes['globalaccelerator'] = GlobalAcceleratorAnalyser
    analyser_classes['rds'] = RDSAnalyser
    analyser_classes['memorydb'] = MemoryDBAnalyser
    analyser_classes['dx'] = DXAnalyser

    def __init__ (self):
        #self.services = services
        #self.regions = regions
        self.lock = threading.Lock()
        self.threads = []
        self.account_name = ''
        self.payer_account_id = ''
        self.payer_account_name = ''
        self.run_report = []

        utils.get_config_info()

        self.account_id = utils.config_info.account_id
        self.thread_limiter = threading.BoundedSemaphore(utils.config_info.max_concurrent_threads)

        #Write out an empty csv file with the headers
        self.keys = [
                        'service',
                        'region',
                        'account_id',
                        'account_name',
                        'payer_account_id',
                        'payer_account_name',
                        'resource_arn',
                        'resource_name',
                        'resource_id',
                        'potential_single_az_risk',
                        'engine', #Used for Elasticache, Memory DB and RDS
                        'message',
                        'timestamp'
                    ]

        self.get_account_level_information()

        curr_time = datetime.datetime.now()
        tm = curr_time.strftime("%Y_%m_%d")

        #Build output file names, either with or without the account id based on the config information
        if utils.config_info.filename_with_accountid:
            self.output_file_name = f"Resiliency_Findings_{self.account_id}_{self.account_name}_{tm}.csv"
            self.run_report_file_name = f"Resiliency_Findings_{self.account_id}_{self.account_name}_{tm}_run_report.csv"
        else:
            self.output_file_name = f"Resiliency_Findings_{tm}.csv"
            self.run_report_file_name = f"Resiliency_Findings_{tm}_run_report.csv"

        self.output_file_full_path = f"{utils.config_info.output_folder_name}{self.output_file_name}"
        self.run_report_file_full_path = f"{utils.config_info.output_folder_name}{self.run_report_file_name}"

        self.create_or_truncate_file = False

        if utils.config_info.truncate_output:
            self.create_or_truncate_file = True #If truncate mode is set to True, then create/truncate file
        else:
            if not os.path.isfile(self.output_file_full_path):
                self.create_or_truncate_file = True #If truncate mode is set to False but file does not already exist, then create the file

        #If the folder does not exist, create it.
        os.makedirs(os.path.dirname(utils.config_info.output_folder_name), exist_ok=True)

        if self.create_or_truncate_file: #If create or truncate file is true then open the file in 'w' mode and write the header
            with open(self.output_file_full_path, 'w', newline='') as output_file:
                dict_writer = csv.DictWriter(output_file, self.keys)
                dict_writer.writeheader()

    def get_findings(self):
        start = datetime.datetime.now().astimezone()

        for region in utils.config_info.regions:
            for service in utils.config_info.services:
                analyser = self.analyser_classes[service](account_analyser = self, region = region)        
                if utils.config_info.single_threaded:
                    analyser.get_and_write_findings()
                else:
                    t = threading.Thread(target = analyser.get_and_write_findings, name = f"{service}+{region}")
                    self.threads.append(t)
                    t.start()

        #If running in multi threaded mode wait for all threads to finish
        if not utils.config_info.single_threaded:
            for t in self.threads:
                t.join()

        end = datetime.datetime.now().astimezone()

        self.run_report.append(
                                {
                                'account_id' : self.account_id,
                                'region'  : 'Overall',
                                'service' : 'Overall',
                                'result'  : 'N/A', 
                                'error_message' : 'N/A',
                                'start_time' : start.strftime("%Y_%m_%d_%H_%M_%S%z"),
                                'end_time' : end.strftime("%Y_%m_%d_%H_%M_%S%z"),
                                'runtime_in_seconds' : round((end-start).total_seconds(), 2)
                                }
                            )

        logging.info(f"Total time taken for the account {self.account_id} is {end-start} seconds")
        self.write_run_report()

        if utils.config_info.bucket_name:
            self.push_files_to_s3()

    def write_run_report(self):
        run_report_keys = self.run_report[0].keys()
        if self.create_or_truncate_file: #Same behaviour as the findings output file. If a new findings file is created or it is truncated, then create or truncate the run_report too.
            file_open_mode = 'w'
        else:
            file_open_mode = 'a+'
        with open(self.run_report_file_full_path, file_open_mode, newline='') as output_file:
            dict_writer = csv.DictWriter(output_file, run_report_keys)
            if self.create_or_truncate_file:
                dict_writer.writeheader()
            dict_writer.writerows(self.run_report)

    def push_files_to_s3(self):
        session = utils.get_aws_session(session_name = 'UploadFilesToS3')
        s3 = session.client("s3")
        try:
            response = s3.upload_file(self.output_file_full_path, utils.config_info.bucket_name, utils.config_info.output_folder_name+self.output_file_name)
            logging.info(f"Uploaded output file {utils.config_info.output_folder_name+self.output_file_name} to bucket {utils.config_info.bucket_name}")
 
            response = s3.upload_file(self.run_report_file_full_path, utils.config_info.bucket_name, utils.config_info.output_folder_name+self.run_report_file_name)
            logging.info(f"Uploaded run report file {utils.config_info.output_folder_name+self.output_file_name} to bucket {utils.config_info.bucket_name}")

        except botocore.exceptions.ClientError as error:
            logging.error(error)

    def get_account_level_information(self):
        session = utils.get_aws_session(session_name = 'InitialAccountInfoGathering')
        org = session.client("organizations")
        try:
            acct_info = org.describe_account(AccountId = self.account_id)
            self.account_name = acct_info["Account"]["Name"]
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'AWSOrganizationsNotInUseException':
                logging.info(f"Account {self.account_id} is not part of an AWS Organization")
                self.account_name = ''
                self.payer_account_id = 'N/A'
                self.payer_account_name = 'N/A'
                return
            else:
                raise error

        org_info = org.describe_organization()
        self.payer_account_id = org_info["Organization"]["MasterAccountId"]

        payer_account_info = org.describe_account(AccountId = self.payer_account_id)
        self.payer_account_name = payer_account_info["Account"]["Name"]

if __name__ == "__main__":
    #Create an instance of the Account level analyser and trigger the get_findings function.
    ara = AccountResiliencyAnalyser()
    ara.get_findings()
