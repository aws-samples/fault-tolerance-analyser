# Resiliency Analyser

## __Table of Contents__
1. [Description](#1-description)
2. [Motivation](#2-motivation)
3. [Permissions needed to run the tool](#3-permissions-needed-to-run-the-tool)
4. [Installation](#4-installation)
5. [Running the tool using Python directly](#5-running-the-tool-using-python-directly)
6. [Running the tool as a Docker container](#6-running-the-tool-as-a-docker-container)
7. [Functional Design](#7-functional-design)  
  7.1 [VPC Endpoints](#71-vpc-endpoints)  
  7.2 [Database Migration Service](#72-database-migration-service)  
  7.3 [DocumentDB Clusters](#73-documentdb)  
  7.4 [Storage Gateway](#74-storage-gateway)  
  7.5 [Elastic File System](#75-elastic-file-system)  
  7.6 [Opensearch](#76-opensearch)  
  7.7 [FSX](#77-fsx)  
  7.8 [Lambda](#78-lambda)  
  7.9 [Elasticache](#79-elasticache)  
  7.10 [Memory DB](#710-memory-db)  
  7.11 [DynamoDB Accelerator](#711-dynamodb-accelerator)  
  7.12 [Global Accelerator](#712-global-accelerator)  
  7.13 [Relational Database Service](#713-relational-database-service)   
  7.14 [Direct Connect](#714-direct-connect)  
  7.15 [Cloud HSM](#715-cloud-hsm)  
8. [Non-Functional Design](#8-non-functional-design)
9. [Security](#9-security)
10. [License](#10-license)

## __1. Description__
A tool to generate a list of potential resiliency risks across different services. Please note that these are only *potential* risks.

There are a number of circumstances in which this may not pose a risk including, development workloads, cost, or not viewing this workload as a business risk in the event of an AZ impacting event.

The output is a csv file created locally and also uploaded to an S3 bucket (if provided).

## __2. Motivation__
The intent is to help customers check their workloads for any obvious situations where there is a lack of Resiliency/high availability.

## __3. Permissions needed to run the tool__

You can run the script on an EC2 with an instance role, or on your own machine with the credentials exported using the usual AWS env variables (as below) or with a profile configured using `aws configure` CLI command

```
export AWS_ACCESS_KEY_ID=abc
export AWS_SECRET_ACCESS_KEY=def
export AWS_SESSION_TOKEN=ghi
```

These credentials are needed as the code will invoke AWS APIs to get information about different AWS services. Except when pushing the output file to the S3 bucket, assume_role API call if a role is passed in, all other operations are "read-only". Here are the list of APIs invoked:

```
#APIs invoked for common functionality like getting account information, list of regions, etc.
STS.get_caller_identity
STS.assume_role
EC2.describe_regions
Organizations.describe_account
S3.put_object

#APIs invoked for service specific resiliency analysis
Lambda.list_functions
StorageGateway.list_gateways
OpenSearchService.list_domain_names
OpenSearchService.describe_domains
OpenSearchService.describe_domain
ElastiCache.describe_cache_clusters
ElastiCache.describe_replication_groups
EFS.describe_file_systems
DirectConnect.describe_connections
DirectConnect.describe_virtual_interfaces
FSx.describe_file_systems
MemoryDB.describe_clusters
DAX.describe_clusters
DatabaseMigrationService.describe_replication_instances
RDS.describe_db_instances
RDS.describe_db_clusters
EC2.describe_vpc_endpoints
EC2.describe_instances
```

You can also provide an IAM role that the above provided profile can assume.

If you want the least privileged policy to run this, the minimal permissions needed can be seen in minimal_IAM_policy.json. While most of the policy uses * format to provide permissions (because the tool needs to look at all resources of a specific type), but it is a good practice to specify the account id and a specific bucket name. So please replace all occurences of `account_id`, `bucket_name` and `output_folder_name` with the appropriate values. If you are passing an event bus arn to the tool to post events to the bus, then make sure you use the last section in the minimal_IAM_policy.json after modifying the `account_id`, `event-bus-region` and `event_bus_name`. If the event bus is in an account different from where the tool is being run, then make sure the resource policy on the event bus allows posting events from account the tool is running from. Reder to the [Example policy to send custom events in a different bus](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-bus-perms.html#eb-event-bus-example-policy-cross-account-custom-bus-source)

The minimal IAM policy is written in a way that you can remove sections for the resource types that you do not want the tool to look at for your account. If, say, you do not want to run this tool for directconnect, you can remove the section with the sid `DirectConnect`.

In the IAM policy provided, some SIDs have the suffix "ThatSupportAllResources" which means that the API calls included in that section, by default, work on all resources, and that you cannot specify specific resources. So a "*" there does not go against the best practice that wild cards should not be used in IAM policies.

Sections with SIDs that have the suffix "ThatRequireWildcardResources" (used for Dynamo DB Accelerator and Direct Connect) are API calls where using the wildcard is unavoidable.

In all other cases, the region and the resource name/id are wild cards as the tool needs to work across multiple regions and needs to look at all resources.

## __4. Installation__
1. You will need Python 3.10+ for this tool. If you do not have Python installed, please install it from here:
https://www.python.org/

2. Clone the repo and install the dependencies with the following command:
```
pip install -r requirements.txt
```

4. Once this is set up, you can run the tool as described in the next secion

## __5. Running the tool using Python directly__
Here is a simple example commmand on how you can run the script

```
cd src
python3 account_resiliency_analyser.py \
    --regions us-east-1 \
    --services lambda opensearch docdb rds \
    --truncate-output
```

In the command above, the script is run for the us-east-1 region, and looks at the services Lambda, Opensearch, Document DB and RDS. It generates the csv file and writes it to the output sub folder in the folder it is run. The truncate-output option ensures that if there is any existing file it is truncated before the findings are added.

Once the script finishes, check the subfolder output/ and you will see 2 files like below.

```
ls output/

Resiliency_Findings_2022_11_21_17_09_19.csv
Resiliency_Findings_2022_11_21_17_09_19_run_report.csv
```

The output will look like this. This shows all the findings.

```
service,region,account_id,account_name,payer_account_id,payer_account_name,resource_arn,resource_name,resource_id,potential_single_az_risk,engine,message,timestamp
lambda,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:lambda:us-east-1:123456789101:function:test1z,test1z,,True,,VPC Enabled lambda in only one subnet,2022_11_29_16_20_43_+0000
lambda,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:lambda:us-east-1:123456789101:function:test2az,test2az,,False,,VPC Enabled lambda in more than one subnet,2022_11_29_16_20_43_+0000
docdb,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:rds:us-east-1:123456789101:cluster:docdb-2022-07-08-13-05-30,docdb-2022-07-08-13-05-30,cluster-JKL,True,,Single AZ Doc DB Cluster,2022_11_29_16_20_43_+0000
docdb,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:rds:us-east-1:123456789101:cluster:docdb-2022-07-19-09-35-14,docdb-2022-07-19-09-35-14,cluster-GHI,True,,Single AZ Doc DB Cluster,2022_11_29_16_20_43_+0000
docdb,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:rds:us-east-1:123456789101:cluster:docdb-2022-11-10-12-43-07,docdb-2022-11-10-12-43-07,cluster-DEF,True,,Single AZ Doc DB Cluster,2022_11_29_16_20_43_+0000
docdb,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:rds:us-east-1:123456789101:cluster:docdb-2022-11-10-12-44-23,docdb-2022-11-10-12-44-23,cluster-ABC,True,,Single AZ Doc DB Cluster,2022_11_29_16_20_43_+0000
opensearch,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:es:us-east-1:123456789101:domain/test4,test4,123456789101/test4,True,,Single AZ domain,2022_11_29_16_20_44_+0000
opensearch,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:es:us-east-1:123456789101:domain/test5,test5,123456789101/test5,True,,Single AZ domain,2022_11_29_16_20_44_+0000
opensearch,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:es:us-east-1:123456789101:domain/test2,test2,123456789101/test2,False,,Multi AZ domain,2022_11_29_16_20_44_+0000
opensearch,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:es:us-east-1:123456789101:domain/test3,test3,123456789101/test3,True,,Single AZ domain,2022_11_29_16_20_44_+0000
opensearch,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:es:us-east-1:123456789101:domain/test6,test6,123456789101/test6,True,,Single AZ domain,2022_11_29_16_20_44_+0000
opensearch,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:es:us-east-1:123456789101:domain/test1,test1,123456789101/test1,True,,Single AZ domain,2022_11_29_16_20_44_+0000
rds,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:rds:us-east-1:123456789101:db:database-3,database-3,,True,sqlserver-ex,RDS Instance has MultiAZ disabled,2022_11_29_16_20_44_+0000
rds,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:rds:us-east-1:123456789101:cluster:auroraclustersingleaz,auroraclustersingleaz,,True,aurora-mysql,DB Cluster has MultiAZ disabled,2022_11_29_16_20_44_+0000
rds,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:rds:us-east-1:123456789101:cluster:aurora-mysql-multiaz,aurora-mysql-multiaz,,False,aurora-mysql,DB Cluster has MultiAZ enabled,2022_11_29_16_20_44_+0000
rds,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:rds:us-east-1:123456789101:cluster:database-4,database-4,,False,postgres,DB Cluster has MultiAZ enabled,2022_11_29_16_20_44_+0000
rds,us-east-1,123456789101,TestAccount,999456789101,TestParentAccount,arn:aws:rds:us-east-1:123456789101:cluster:mysql-cluster,mysql-cluster,,False,mysql,DB Cluster has MultiAZ enabled,2022_11_29_16_20_44_+0000
```

The run report will look like this. This gives an idea of how long each service+region combination took.
```
account_id,region,service,result,error_message,start_time,end_time,runtime_in_seconds
625787456381,us-east-1,opensearch,Success,,2022_11_29_16_20_42_+0000,2022_11_29_16_20_43_+0000,1.05
625787456381,us-east-1,lambda,Success,,2022_11_29_16_20_42_+0000,2022_11_29_16_20_43_+0000,1.12
625787456381,us-east-1,docdb,Success,,2022_11_29_16_20_42_+0000,2022_11_29_16_20_44_+0000,1.74
625787456381,us-east-1,rds,Success,,2022_11_29_16_20_42_+0000,2022_11_29_16_20_45_+0000,2.62
625787456381,Overall,Overall,N/A,N/A,2022_11_29_16_20_42_+0000,2022_11_29_16_20_45_+0000,2.68
```

The same files will also be pushed to an S3 bucket if you provide a bucket name as a command line argument. When you provide a bucket, please make sure the bucket is properly secured as the output from this tool will be written to that bucket, and it could contain sensitive information (like names of RDS instances or other configuration detail) that you might not want to share widely.


Use the option --help to look at all the options. Here are the options.

```
python3 account_resiliency_analyser.py --help
usage: account_resiliency_analyser.py -s {vpce,dms,docdb,sgw,efs,opensearch,fsx,lambda,elasticache,dax,globalaccelerator,rds,memorydb,dx,ALL}
                                      [{vpce,dms,docdb,sgw,efs,opensearch,fsx,lambda,elasticache,dax,globalaccelerator,rds,memorydb,dx,ALL} ...] -r REGIONS [REGIONS ...] [-h]
                                      [-m MAX_CONCURRENT_THREADS] [-o OUTPUT_FOLDER_NAME] [-b BUCKET_NAME] [--event-bus-arn EVENT_BUS_ARN] [--aws-profile AWS_PROFILE_NAME]
                                      [--aws-assume-role AWS_ASSUME_ROLE_NAME] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--single-threaded] [--truncate-output] [--filename-with-accountid]
                                      [--report-only-risks]

Generate resiliency findings for different services

Required arguments:
  -s {vpce,dms,docdb,sgw,efs,opensearch,fsx,lambda,elasticache,dax,globalaccelerator,rds,memorydb,dx,ALL} [{vpce,dms,docdb,sgw,efs,opensearch,fsx,lambda,elasticache,dax,globalaccelerator,rds,memorydb,dx,cloudhsm,ALL} ...], --services {vpce,dms,docdb,sgw,efs,opensearch,fsx,lambda,elasticache,dax,globalaccelerator,rds,memorydb,dx,cloudhsm,ALL} [{vpce,dms,docdb,sgw,efs,opensearch,fsx,lambda,elasticache,dax,globalaccelerator,rds,memorydb,dx,cloudhsm,ALL} ...]
                        Indicate which service(s) you want to fetch resiliency findings for. Options are ['vpce', 'dms', 'docdb', 'sgw', 'efs', 'opensearch', 'fsx', 'lambda', 'elasticache', 'dax',
                        'globalaccelerator', 'rds', 'memorydb', 'dx', 'cloudhsm']. Use 'ALL' for all services
  -r REGIONS [REGIONS ...], --regions REGIONS [REGIONS ...]
                        Indicate which region(s) you want to fetch resiliency findings for. Use "ALL" for all approved regions

Optional arguments:
  -h, --help            show this message and exit
  -m MAX_CONCURRENT_THREADS, --max-concurrent-threads MAX_CONCURRENT_THREADS
                        Maximum number of threads that will be running at any given time. Default is 20
  -o OUTPUT_FOLDER_NAME, --output OUTPUT_FOLDER_NAME
                        Name of the folder where findings output csv file and the run report csv file will be written. If it does not exist, it will be created. If a bucket name is also provided, then
                        the folder will be looked for under the bucket, and if not present, will be created If a bucket name is not provided, then this folder will be expected under the directory in
                        which the script is ran. In case a bucket is provided, the files will be generated in this folder first and then pushed to the bucket Please ensure there is a forward slash '/'
                        at the end of the folder path Output file name will be of the format Resiliency_Findings_<account_id>_<account_name>_<Run date in YYYY_MM_DD format>.csv. Example:
                        Resiliency_Findings_123456789101_TestAccount_2022_11_01.csv If you do not use the --filename-with-accountid option, the output file name will be of the format:
                        Resiliency_Findings_<Run date in YYYY_MM_DD format>.csv. Example: Resiliency_Findings_2022_11_01.csv
  -b BUCKET_NAME, --bucket BUCKET_NAME
                        Name of the bucket where findings output csv file and the run report csv file will be uploaded to
  --event-bus-arn EVENT_BUS_ARN
                        ARN of the event bus in AWS Eventbridge to which findings will be published.
  --aws-profile AWS_PROFILE_NAME
                        Use this option if you want to pass in an AWS profile already congigured for the CLI
  --aws-assume-role AWS_ASSUME_ROLE_NAME
                        Use this option if you want the aws profile to assume a role before querying Org related information
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Log level. Needs to be one of the following: 'DEBUG','INFO','WARNING','ERROR','CRITICAL'
  --single-threaded     Use this option to specify that the service+region level information gathering threads should not run in parallel. Default is False, which means the script uses multi-threading
                        by default. Same effect as setting max-running-threads to 1
  --truncate-output     Use this flag to make sure that if the output file already exists, the file is truncated. Default is False. Useful if you are invoking this script to refresh findings within
                        the same day (on a different day, the output file will have a different file name)
  --filename-with-accountid
                        Use this flag to include account id in the output file name. By default this is False, meaning, account id will not be in the file name. The default mode is useful if you are
                        running the script for more than one account, and want all the accounts' findings to be in the same output file.
  --report-only-risks   Use this flag to report only findings that are potential risks. Resources that have no identified risks will not appear in the final csv file. Default is to report all
                        findings.


```

## __6. Running the tool as a Docker container__

Instead of installing Python and the dependencies, you can just use the Docker file and run the tool as a container. Here is how to do it.

1. Clone the repo and bulid the image by running the command `docker build . -t resiliency_analyser`

2. If you are using an AWS profile use the following command (note how the credentials file is mapped into the container so that the container will have access to the credentials). Also note that the volume being mapped is the folder into which the output file to be written.If the folder(s) given in the path does not exist, the container will create it.

```
docker run \
    -v $HOME/.aws/credentials:/root/.aws/credentials:ro \
    -v $PWD/src/output/:/src/output/:rw \
    org_visualiser \
    --aws-profile madhav \
    -o output/output.html
```

3. If you are using AWS credentials exported as env variables you can run it as below. You can remove AWS_SESSION_TOKEN if you are using long term credentials

```
docker run \
    -v $PWD/src/output/:/src/output/:rw \
    -e AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY \
    -e AWS_SESSION_TOKEN \
    resiliency_analyser \
    --regions us-east-1 \
    --services lambda opensearch docdb rds \
    --truncate-output
```

4. If you are running on an EC2 machine with an IAM role associated with the machine, then you can just run it without env variables or credential files as below.

```
docker run \
    -v $PWD/src/output/:/src/output/:rw \
    resiliency_analyser \
    --regions us-east-1 \
    --services lambda opensearch docdb rds \
    --truncate-output
```

## __7. Functional Design__

### 7.1 VPC Endpoints
It is a best practice to make sure that VPC Interface Endpoints have ENIs in more than one subnet. If a VPC endpoint has an ENI in only a single subnet, this tool will flag that as a potential risk. You cannot create VPC Endpoints in 2 different subnets in the same AZ. So, for the purpose of VPC endpoints, having multiple subnets implies multiple AZs.

### 7.2 Database Migration Service
If the DMS Replication Instance is not configured with at least 2 instances in different availability zones, then it will be tagged as a potential risk.

Reference: https://docs.aws.amazon.com/dms/latest/userguide/CHAP_ReplicationInstance.html

### 7.3 DocumentDB
If the Document DB Cluster does not have a replica in a different AZ, it will be tagged as a potential risk.

Reference: https://docs.aws.amazon.com/documentdb/latest/developerguide/failover.html

### 7.4 Storage Gateway
Storage Gateway, when deployed on AWS, runs on a single Amazon EC2 instance. Therefore this is a single-point of availability failure for any applications expecting highly available access to application storage. Such storage gateways will be tagged as part of this check as a potential risk.

Customers who are running Storage Gateway as a mechanism for providing file-based application storage that require high-availability should consider migrating their workloads to Amazon EFS, FSx, or other storage services that can provide higher availability architectures than Storage Gateway.

### 7.5 Elastic File System
This check tags both of the following scenarios as potential risks:
1. Running an "EFS One Zone" deployment
2. Running "EFS Standard" class deployment with a mount target in only one AZ.

Customers that have chosen to deploy a One Zone class of storage, should ensure these workloads are not "mission-critical" that require high-availability and that the choice was made appropriately.

For customers identified that are running a Standard class EFS deployment, where multi-az replication is provided by the service, they have only a single mount target to access their file systems.  If an availability issue were to occur in that availability zone, the customer would lose access to the EFS deployment, even though other AZs/subnets were unaffected.

### 7.6 Opensearch
Any single-node domains, as well as OpenSearch domains with multiple nodes all of which are deployed within the same Availability Zone would be tagged as a potential risk by this tool.

### 7.7 FSx
Any FSx Windows systems deployed as Single-AZ is tagged as a potential risk by this tool.

Customers have the option to choose a Mulit-AZ or Single-AZ deployment when creating their file server deployment.

### 7.8 Lambda
Any Lambda function that is configured only to execute in a single Availability Zone are tagged as a potential risk.
Reference: https://docs.aws.amazon.com/lambda/latest/dg/security-resilience.html

### 7.9 Elasticache
The following clusters are tagged as potential Single AZ risks

1. All Memcached clusters - Data is not replicated between memcached cluster nodes. Even if a customer has deployed nodes across multiple availability zones, the data present on any nodes that have a loss of availability (related to those hosts or their AZ) will result in the data in those cache nodes being unavailable as well.

2. Redis clusters - The following clusters are taggeed as a risk  
  2.1 Any single node clusters  
  2.2 Any "Cluster Mode" disabled clusters.  
  2.3 Any "Cluster Mode" enabled clusters with at least one Node group having all the nodes in the same AZ.  
  2.4 "Cluster Mode" enabled clusters but Auto Failover disabled.  
  2.5 "Cluster Mode" enabled clusters having shards with no replicas.  
  
  Reference: https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/Replication.Redis-RedisCluster.html

### 7.10 Memory DB
Any Memory DB cluster that has a single node in a shard  is tagged as a potential risk by this tool.

### 7.11 DynamoDB Accelerator
Any single-node clusters, as well as DAX clusters with multiple nodes all deployed within the same Availability Zone would be tagged as being a potential risk by this tool.

### 7.12 Global Accelerator
Any "Standard" Global accelerators that are configured to target endpoints consisting only of EC2 instances in a single Availability Zone are flagged by this tool. "Custom Routing" Global Accelerators are not covered.

### 7.13 Relational Database Service
Any single AZ RDS Instance or Cluster is tagged as a potential risk by this tool.

### 7.14 Direct Connect
The following scenarios are tagged as potential risk by this tool:
1. Any region with a single Direct Connect connection.
2. Any region where there is more than one direct connection, but all of them use the same location.
3. Any Virtual Gateway with only one VIF
4. Any Virtual Gateway with more than one VIF but all of the VIFs on the same direct connect Connection.

### 7.15 Cloud HSM
The following scenarios are tagged as potential risk by this tool:
1. Any cluster with a single HSM.
2. Any cluster with multiple HSMs all of which are in a single AZ.

## __8. Non-Functional Design__

There are two main classes:

### ServiceResiliencyAnalyser
The ServiceResiliencyAnalyser is an abstract class from which all the service specific analysers are inherited. The service specific analysers contain the logic to identify potential risks for a given region.

### AccountResiliencyAnalyser
An object of this class is initiated as part of the "main" functionality. This loops through all the services and regions and instantiates the service specific analyser for each region+service combination and triggers the method to gather the findings in that service specific analyser. Once the findings are received, it writes it to a file.

The AccountResiliencyAnalyser logic can run either in multi-threaded or single-threaded mode. In multi-threaded mode, the analyser for each service+region combination runs in a separate thread. This is the default mode. This saves a lot of time as there are 14 analysers running making API calls and that too across multiple regions.

In multi-threaded mode, care is taken to ensure that when writing the findings to an output file, multiple threads do not try to do it at the same time (with the help of a lock).

When all the analysers are run, the output file is uploaded to an S3 bucket, if provided.

## __9. Security__

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## __10. License__

This library is licensed under the MIT-0 License. See the LICENSE file.
