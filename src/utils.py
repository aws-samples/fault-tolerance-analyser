# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import argparse
import logging
import re
import time
import threading
import boto3
import botocore
from datetime import datetime, date
from dataclasses import dataclass


@dataclass
class ConfigInfo:
    regions: list
    services: list
    max_concurrent_threads: int
    output_folder_name: str
    event_bus_arn: str
    log_level: str
    aws_profile_name: str
    aws_assume_role_name: str
    single_threaded: bool
    run_report_file_name: str
    bucket_name: str
    account_id: str
    truncate_output: bool
    filename_with_accountid: bool
    report_only_issues: bool

all_services = ['vpce',
                'dms',
                'docdb',
                'sgw',
                'efs',
                'opensearch',
                'fsx',
                'lambda',
                'elasticache',
                'dax',
                'globalaccelerator',
                'rds',
                'memorydb',
                'dx',
                'cloudhsm']

#Use the below function,if needed, as print(json.dumps(db_instance,  default = json_serialise, indent = 4))
def json_serialise(obj):
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d, %H:%M:%S %Z")
    elif isinstance(obj, date):
        return obj.strftime("%Y-%m-%d %Z")
    else:
        raise TypeError (f"Type {type(obj)} not serializable")

#Reference: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html
def regex_validator_generator(regex, desc_param_name, custom_message = ""):
    pattern = re.compile(regex)
    def regex_validator(arg_value):
        if arg_value is None:
            return arg_value
        elif not pattern.match(arg_value):
            raise argparse.ArgumentTypeError(f"Invalid {desc_param_name}. {custom_message}")
        return arg_value
    return regex_validator

def maxlen_validator_generator(max_len, desc_param_name):
    def maxlen_validator(arg_value):
        if arg_value is None:
            return arg_value
        elif len(arg_value) > max_len:
            raise argparse.ArgumentTypeError(f"{desc_param_name} too long. It should not exceed {max_len} characters.")
        return arg_value
    return maxlen_validator

def log_func(func):
    def inner(*args, **kwargs): 
        logging.debug(f"In thread {threading.current_thread().name}: Starting {func.__name__} with args: {args} and key word args: {kwargs}")
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logging.info(f"Completed {func.__name__} in thread {threading.current_thread().name} with args: {args} and key word args: {kwargs} in {end-start} seconds.")
        return result
    return inner

def get_aws_session(session_name = None):
    session = boto3.session.Session(profile_name = config_info.aws_profile_name)

    if config_info.aws_assume_role_name: #Need to assume a role before creating an org client
        
        logging.info(f"aws-assume-role option is used. About to assume the role {config_info.aws_assume_role_name}")

        sts_client = session.client('sts')
        account_id = sts_client.get_caller_identity()["Account"]

        if not session_name:
            session_name = "AssumeRoleForFaultToleranceAnalyser"

        assumed_role_object=sts_client.assume_role(
            RoleArn=f"arn:aws:iam::{account_id}:role/{config_info.aws_assume_role_name}",
            RoleSessionName=session_name
        )
        credentials=assumed_role_object['Credentials']

        assumed_role_session = boto3.session.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
        )
        logging.info(f"Assumed the role {config_info.aws_assume_role_name} with session name {session_name}")
        return assumed_role_session
    else:
        return session

def check_aws_credentials():
    try:
        session = boto3.session.Session(profile_name = config_info.aws_profile_name)
        sts = session.client("sts")
        resp = sts.get_caller_identity()
        account_id = resp["Account"]
        return account_id
    except botocore.exceptions.ClientError as error:
        raise error

def get_approved_regions():
    session = get_aws_session(session_name = 'ValidateRegions')
    ec2 = session.client("ec2", region_name='us-east-1')
    response = ec2.describe_regions()
    approved_regions = [region["RegionName"] for region in response["Regions"]]
    return approved_regions

def regions_validator(input_regions):

    approved_regions = get_approved_regions()

    if 'ALL' in input_regions:
        if len(input_regions) == 1: #'ALL' is the only input
            return approved_regions
        else:
            raise argparse.ArgumentTypeError(f"When providing 'ALL' as an input region, please do not provide any other regions. 'ALL' implies all approved regions.")
    else:
        for input_region in input_regions:
            if input_region not in approved_regions:
                raise argparse.ArgumentTypeError(f"{input_region} is not in the list of approved regions for this account. Please provide only approved regions, or specify ALL for all regions that are approved")
    return input_regions

def services_validator(input_services):
    if 'ALL' in input_services:
        if len(input_services) == 1: #'ALL' is the only input
            return all_services
        else:
            raise argparse.ArgumentTypeError(f"When providing 'ALL' as an input service, please do not provide any other services. 'ALL' implies the following services: {all_services}")
    else:
        return input_services

def bus_arn_validator(event_bus_arn):

    if event_bus_arn is None:
        return event_bus_arn

    arn_parts = parse_arn(event_bus_arn)

    #ARN is validated. Now check if the region is correct.
    if arn_parts['region'] == 'ALL':
        raise argparse.ArgumentTypeError(f"Invalid region in event bus arn")
    else:
        approved_regions = get_approved_regions()
        if arn_parts['region'] not in approved_regions:
            raise argparse.ArgumentTypeError(f"{arn_parts['region']} is not in the list of approved regions for this account. Please provide an event bus in an approved regions")
    
    #Check if the resource is in the right format
    bus_name_regex = r"^[A-Za-z0-9._-]{1,256}$"
    bus_name_pattern = re.compile(bus_name_regex)

    if arn_parts['resource_type'] != "event-bus":
        raise argparse.ArgumentTypeError(f"Resource type '{arn_parts['resource_type']}' in the ARN is not valid for an event bus ARN. It should be 'event-bus'")
    elif not bus_name_pattern.match(arn_parts['resource_id']):
        raise argparse.ArgumentTypeError(f"{arn_parts['resource_id']} is not a valid bus name. Maximum of 256 characters consisting of numbers, lower/upper case letters, .,-,_.")

    return event_bus_arn

def arn_validator(arn):
    regex = r"^arn:(aws|aws-gov|aws-cn):.*:.*:.*:.*/$"
    pattern = re.compile(regex)
    if not pattern.match(arn):
        raise argparse.ArgumentTypeError(f"The provided ARN is invalid. Please provide a valid ARN. Ref: https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html")
    return arn

def bucket_name_validator(bucket_name):

    regex = r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
    pattern = re.compile(regex)
    if not (3 <= len(bucket_name) <= 63):
        raise argparse.ArgumentTypeError(f"Invalid bucket name. It must be between 3 and 63 characters in length")
    if not pattern.match(bucket_name):
        raise argparse.ArgumentTypeError(f"Invalid bucket name. Bucket names must be between 3 (min) and 63 (max) characters long. Bucket names can consist only of lowercase letters, numbers, dots (.), and hyphens (-). Bucket names must begin and end with a letter or number.")
    if ".." in bucket_name:
        raise argparse.ArgumentTypeError(f"Invalid bucket name. Bucket names should not have consecutive periods '..' ")
    if bucket_name.startswith("xn--") or bucket_name.endswith('-s3alias'):
        raise argparse.ArgumentTypeError(f"Invalid bucket name. Bucket names should not start with 'xn--' or end with '-s3alias'")
    
    return bucket_name


def get_config_info():

    #Define the arguments
    parser = argparse.ArgumentParser(description='Generate fault tolerance findings for different services', add_help=False)

    required_params_group = parser.add_argument_group('Required arguments')
    required_params_group.add_argument('-s', '--services', nargs='+', choices = all_services + ['ALL'],
                        help=f"Indicate which service(s) you want to fetch fault tolerance findings for. Options are {all_services}. Use 'ALL' for all services",
                        required = True
                        )
    required_params_group.add_argument('-r', '--regions', nargs='+',
                        help='Indicate which region(s) you want to fetch fault tolerance findings for. Use "ALL" for all approved regions',
                        required = True
                        )

    optional_params_group = parser.add_argument_group('Optional arguments')
    optional_params_group.add_argument('-h', '--help', action="help", help = "show this message and exit")

    optional_params_group.add_argument('-m', '--max-concurrent-threads', dest='max_concurrent_threads',
                        default = 20,
                        type=int,
                        help='Maximum number of threads that will be running at any given time. Default is 20')
    optional_params_group.add_argument('-o', '--output', dest='output_folder_name',
                        default='output/',
                        type=regex_validator_generator(regex = r".+/$", desc_param_name = "Output folder name",
                        custom_message = "Provide an output folder name where the findings csv and the run report csv will be placed"),
                        help='''Name of the folder where findings output csv file and the run report csv file will be written. 
                            If it does not exist, it will be created. If a bucket name is also provided, then the folder will be looked for under the bucket, and if not present, will be created
                            If a bucket name is not provided, then this folder will be expected under the directory in which the script is ran. In case a bucket is provided, the files will be generated in this folder first and then pushed to the bucket
                            Please ensure there is a forward slash '/' at the end of the folder path
                            Output file name will be of the format Fault_Tolerance_Findings_<account_id>_<account_name>_<Run date in YYYY_MM_DD format>.csv. Example: Fault_Tolerance_Findings_123456789101_TestAccount_2022_11_01.csv
                            If you do not use the --filename-with-accountid option, the output file name will be of the format:
                            Fault_Tolerance_Findings_<Run date in YYYY_MM_DD format>.csv. Example: Fault_Tolerance_Findings_2022_11_01.csv''')
    optional_params_group.add_argument('-b', '--bucket', dest='bucket_name',
                        default = None,
                        type=bucket_name_validator,
                        help='Name of the bucket where findings output csv file and the run report csv file will be uploaded to')
    optional_params_group.add_argument('--event-bus-arn', dest='event_bus_arn',
                        default=None,
                        type=regex_validator_generator(regex = r"arn:(aws|aws-gov|aws-cn):events:.*:.*:event-bus*/[A-Za-z0-9._-]{1,256}$", desc_param_name = "Event Bus ARN",
                        custom_message = "Provide the ARN of an event bus in AWS Eventbridge to which findings will be published"),
                        help='''ARN of the event bus in AWS Eventbridge to which findings will be published.''')
    optional_params_group.add_argument('--aws-profile', dest='aws_profile_name',
                        default=None,
                        type=maxlen_validator_generator(max_len = 250,desc_param_name = "AWS Profile name"),
                        help="Use this option if you want to pass in an AWS profile already congigured for the CLI")
    optional_params_group.add_argument('--aws-assume-role', dest='aws_assume_role_name',
                        default=None,
                        type=regex_validator_generator(regex = r"^[a-zA-Z0-9+=,.@_-]+$", desc_param_name = "IAM Role name"),
                        #type=iam_entity,
                        help="Use this option if you want the aws profile to assume a role before querying Org related information")
    optional_params_group.add_argument('--log-level', dest='log_level',
                        default='ERROR', choices = ['DEBUG','INFO','WARNING','ERROR','CRITICAL'],
                        help="Log level. Needs to be one of the following: 'DEBUG','INFO','WARNING','ERROR','CRITICAL'")
    optional_params_group.add_argument('--single-threaded', action='store_true', dest='single_threaded',
                        default=False,
                        help="Use this option to specify that the service+region level information gathering threads should not run in parallel. Default is False, which means the script uses multi-threading by default. Same effect as setting max-running-threads to 1")
    optional_params_group.add_argument('--truncate-output', action='store_true', dest='truncate_output',
                        default=False,
                        help="Use this flag to make sure that if the output file already exists, the file is truncated. Default is False. Useful if you are invoking this script to refresh findings within the same day (on a different day, the output file will have a different file name)")
    optional_params_group.add_argument('--filename-with-accountid', action='store_true', dest='filename_with_accountid',
                        default=False,
                        help='''Use this flag to include account id in the output file name. 
                        By default this is False, meaning, account id will not be in the file name. 
                        The default mode is useful if you are running the script for more than one account,
                        and want all the accounts' findings to be in the same output file.''')
    optional_params_group.add_argument('--report-only-issues', action='store_true', dest='report_only_issues',
                        default=False,
                        help="Use this flag to report only findings that are potential issues. Resources that have no identified issues will not appear in the final csv file. Default is to report all findings.")
    args = parser.parse_args()

    #Set up logging
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=args.log_level,
        datefmt='%Y-%m-%d %H:%M:%S')

    global config_info

    config_info = ConfigInfo(
                            regions = [],
                            services = [],
                            max_concurrent_threads = args.max_concurrent_threads,
                            output_folder_name = args.output_folder_name,
                            event_bus_arn=args.event_bus_arn,
                            log_level = args.log_level,
                            aws_profile_name = args.aws_profile_name,
                            aws_assume_role_name = args.aws_assume_role_name,
                            single_threaded = args.single_threaded,
                            run_report_file_name = "run_report.csv",
                            bucket_name = args.bucket_name,
                            account_id = '',
                            truncate_output = args.truncate_output,
                            filename_with_accountid = args.filename_with_accountid,
                            report_only_issues = args.report_only_issues
                )


    #First check credentials
    account_id = check_aws_credentials()

    #Validate regions
    config_info.account_id = account_id
    config_info.regions = regions_validator(args.regions)
    config_info.services = services_validator(args.services)
    config_info.event_bus_arn = bus_arn_validator(args.event_bus_arn)

def invoke_aws_api_full_list (api_method, top_level_member, **kwargs):

    logging.info(f"Invoking {api_method.__self__.__class__.__name__}.{api_method.__name__} for {top_level_member} with the parameters {kwargs}")
    response = api_method(**kwargs)

    for response_item in response[top_level_member]:
        yield(response_item)

    while ('NextToken' in response):
        response = api_method(NextToken = response['NextToken'], **kwargs)
        for response_item in response[top_level_member]:
            yield(response_item)

def parse_arn(arn):
    parts = arn.split(":")
    if len(parts) == 7: #Follows the format "arn:partition:service:region:account-id:resource-type:resource-id"
        result = {
            'arn': parts[0],
            'partition': parts[1],
            'service': parts[2],
            'region': parts[3],
            'account_id': parts[4],
            'resource_type': parts[5],
            'resource_id': parts[6]
        }
    elif len(parts) == 6:
        if "/" in parts[5]: #Follows the format "arn:partition:service:region:account-id:resource-type/resource-id"
            resource_info = parts[5]
            resource_parts = resource_info.split("/")
            result = {
                'arn': parts[0],
                'partition': parts[1],
                'service': parts[2],
                'region': parts[3],
                'account_id': parts[4],
                'resource_type': resource_parts[0],
                'resource_id': resource_parts[1],
            }
        else: #follows the format #Follows the format "arn:partition:service:region:account-id:resource-id"
            result = {
                'arn': parts[0],
                'partition': parts[1],
                'service': parts[2],
                'region': parts[3],
                'account_id': parts[4],
                'resource_type': None,
                'resource_id': parts[5],
            }
    else:
        raise argparse.ArgumentTypeError(f"Invalid ARN. Does not follow the pattern defined here: https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html")

    return result
