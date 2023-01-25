# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from abc import ABCMeta, abstractmethod
import utils
from collections import namedtuple
import botocore
import time
import logging
import datetime

class ServiceResiliencyAnalyser(metaclass = ABCMeta):

    def __init__ (self, account_analyser, region, service):
        self.service = service
        self.region = region
        self.account_analyser = account_analyser
        self.findings = []

    def get_aws_session(self):
        return utils.get_aws_session(session_name = f"{self.service}_{self.region}_ResiliencyAnalyser")

    @utils.log_func
    def get_and_write_findings(self):
        
        with self.account_analyser.thread_limiter:
            start = datetime.datetime.now().astimezone()
            
            try:
                self.get_findings()
                self.account_analyser.write_findings(self.findings)
                end = datetime.datetime.now().astimezone()
                logging.info(f"Completed processing {self.service}+{self.region} in {round((end-start).total_seconds(), 2)} seconds.")
                self.account_analyser.run_report.append(
                                                            {   
                                                            'account_id' : self.account_analyser.account_id,
                                                            'region'  : self.region,
                                                            'service' : self.service,
                                                            'result'  :'Success',
                                                            'error_message' :'',
                                                            'start_time' : start.strftime("%Y_%m_%d_%H_%M_%S_%z"),
                                                            'end_time' : end.strftime("%Y_%m_%d_%H_%M_%S_%z"),
                                                            'runtime_in_seconds' : round((end-start).total_seconds(), 2)
                                                            }
                                                        )
            except botocore.exceptions.BotoCoreError as error:
                end = datetime.datetime.now().astimezone()
                self.account_analyser.run_report.append(
                                                            {   
                                                            'account_id' : self.account_analyser.account_id,
                                                            'region'  : self.region,
                                                            'service' : self.service,
                                                            'result'  :'Failure', 
                                                            'error_message' : str(error), 
                                                            'start_time' : start.strftime("%Y_%m_%d_%H_%M_%S_%z"),
                                                            'end_time' : end.strftime("%Y_%m_%d_%H_%M_%S_%z"),
                                                            'runtime_in_seconds' : round((end-start).total_seconds(), 2)
                                                            }
                                                        )
                raise error
            

    @abstractmethod
    def get_findings(self, region):
        pass

    def get_finding_rec_with_common_fields(self):
        finding_rec = {}
        finding_rec["account_id"] = self.account_analyser.account_id
        finding_rec["account_name"] = self.account_analyser.account_name
        finding_rec["payer_account_id"] = self.account_analyser.payer_account_id
        finding_rec["payer_account_name"] = self.account_analyser.payer_account_name
        finding_rec['service'] = self.service
        finding_rec['region'] = self.region

        curr_time = datetime.datetime.now().astimezone()
        finding_rec['timestamp'] = curr_time.strftime("%Y_%m_%d_%H_%M_%S_%z")

        return finding_rec
