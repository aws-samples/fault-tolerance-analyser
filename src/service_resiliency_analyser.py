# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from abc import ABCMeta, abstractmethod
import utils
from collections import namedtuple
import botocore
import time
import logging
import datetime
import csv
import json

class ServiceResiliencyAnalyser(metaclass = ABCMeta):

    def __init__ (self, account_analyser, region, service):
        self.service = service
        self.region = region
        self.account_analyser = account_analyser
        self.findings = []
        self.session = None

    def get_aws_session(self):
        if self.session:
            return self.session
        else:
            return utils.get_aws_session(session_name = f"{self.service}_{self.region}_ResiliencyAnalyser")

    @utils.log_func
    def get_and_write_findings(self):
        
        with self.account_analyser.thread_limiter:
            start = datetime.datetime.now().astimezone()
            
            try:
                self.get_findings()
                self.write_findings()
                end = datetime.datetime.now().astimezone()
                logging.info(f"Completed processing {self.service}+{self.region} in {round((end-start).total_seconds(), 2)} seconds.")
                self.account_analyser.run_report.append(
                                                            {   
                                                            'account_id' : self.account_analyser.account_id,
                                                            'region'  : self.region,
                                                            'service' : self.service,
                                                            'result'  :'Success',
                                                            'error_message' :'',
                                                            'start_time' : start.strftime("%Y_%m_%d_%H_%M_%S%z"),
                                                            'end_time' : end.strftime("%Y_%m_%d_%H_%M_%S%z"),
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
                                                            'start_time' : start.strftime("%Y_%m_%d_%H_%M_%S%z"),
                                                            'end_time' : end.strftime("%Y_%m_%d_%H_%M_%S%z"),
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
        finding_rec['timestamp'] = curr_time.strftime("%Y_%m_%d_%H_%M_%S%z")

        return finding_rec

    def write_findings(self):
        self.write_findings_to_file()
        #If an event bus is provided publish any risks to event bridge
        if (utils.config_info.event_bus_arn):
            self.publish_findings_to_event_bridge()

    #This function will be called by the threads to write to the output file. So it must use a lock before opening and writing to the file.
    def write_findings_to_file(self):

        #Log findings
        for finding_rec in self.findings:
            if finding_rec['potential_single_az_risk']:
                logging.error(finding_rec['message'])
            else:
                logging.info(finding_rec['message'])

        #Write findings to output file
        if len(self.findings) > 0:
            keys = self.findings[0].keys()
            if self.account_analyser.lock.acquire():
                with open(self.account_analyser.output_file_full_path, 'a', newline='') as output_file:
                    dict_writer = csv.DictWriter(output_file, self.account_analyser.keys)
                    if utils.config_info.report_only_risks: #If the "report-only-risks" flag is set, go through each finding and write out only those that are identified as a potential risk
                        for finding_rec in self.findings:
                            if finding_rec['potential_single_az_risk']:
                                dict_writer.writerow(finding_rec)
                    else: #If the "report-only-risks" flag is not set, then Write all findings
                        dict_writer.writerows(self.findings)
                self.account_analyser.lock.release()

    def publish_findings_to_event_bridge(self):
        session = self.get_aws_session()

        #Get the event bus region name from the event bus ARN. That region has to be used as cross region API calls are not permitted.
        event_bus_region = (utils.parse_arn(utils.config_info.event_bus_arn))['region']

        events = session.client("events", region_name = event_bus_region)

        entries = []

        total_entries_count = 0

        for finding_rec in self.findings:
            if (not utils.config_info.report_only_risks) or (utils.config_info.report_only_risks and finding_rec['potential_single_az_risk']):
                entries.append(
                    {
                        'Time': datetime.datetime.now().astimezone(),
                        'Source': 'ResiliencyAnalyser',
                        'DetailType': 'ResiliencyRisk',
                        'Detail': json.dumps(finding_rec),
                        'EventBusName' : utils.config_info.event_bus_arn
                    }
                )
                total_entries_count = total_entries_count+1
                if len(entries) == 10: #Call put-events in batches of 10 each because the API does not accept more than that many events in 1 call.
                    response = events.put_events(Entries = entries)
                    events.clear()

        if len(entries) > 0:
            response = events.put_events(Entries = entries)
        
        logging.info(f"Published {total_entries_count} finding(s) for {self.service} in {self.region} to Eventbridge")
