# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import logging
import utils
from service_resiliency_analyser import ServiceResiliencyAnalyser

#Checks the following three.
#1. Direct Connect Connection Redundancy - https://docs.aws.amazon.com/awssupport/latest/user/fault-tolerance-checks.html#aws-direct-connect-connection-redundancy
#2. Direct Connect Location Redundancy - https://docs.aws.amazon.com/awssupport/latest/user/fault-tolerance-checks.html#aws-direct-connect-location-redundancy
#3. Direct Connect Virtual Interface Redundancy - https://docs.aws.amazon.com/awssupport/latest/user/fault-tolerance-checks.html#aws-direct-connect-virtual-interface-redundancy

class DXAnalyser(ServiceResiliencyAnalyser):

    def __init__(self, account_analyser, region):
        super().__init__(account_analyser, region, 'directconnect')

    def get_findings(self):
        self.session = self.get_aws_session()
        self.dx = self.session.client("directconnect", region_name=self.region)
        self.get_conn_location_findings()
        self.get_vif_findings()

    def get_conn_location_findings(self):
        no_of_connections = 0
        locations = set()

        finding_rec = self.get_dx_output()

        for conn in utils.invoke_aws_api_full_list(self.dx.describe_connections, "connections"):
            no_of_connections = no_of_connections + 1
            locations.add(conn["location"])
        
        if no_of_connections == 0: #No DX connection. Hence no risk
            finding_rec['potential_single_az_risk'] = False
            finding_rec['message'] = f"Direct Connect: No connections in region {self.region}. Hence nothing to check"
        elif no_of_connections == 1:
            finding_rec['potential_single_az_risk'] = True
            finding_rec['message'] = f"Direct Connect: There is only one DX connection in region {self.region}"
        else: #no_of_connections > 0 #Connection Redundancy is met.
            logging.info(f"Direct Connect: More than one DX connection found in region {self.region}. Now on to checking locations")
            if len(locations) == 1: #All connections use the same location
                finding_rec['potential_single_az_risk'] = True
                finding_rec['message'] = f"Direct Connect: There is only one location {next(iter(locations))} used by all the DX connections in region {self.region}"
            else: #Connection Redundancy and Location Redundancy is also met
                finding_rec['potential_single_az_risk'] = False
                finding_rec['message'] = f"Direct Connect:  There are more than 1 DX connetions, using more than one location in region {self.region}"

        self.findings.append(finding_rec)

    #check VIF redundancy - https://docs.aws.amazon.com/awssupport/latest/user/fault-tolerance-checks.html#aws-direct-connect-virtual-interface-redundancy
    def get_vif_findings(self):
        
        vifs = {}
        vgws = {}

        #collect all the VIFs
        for vif in utils.invoke_aws_api_full_list(self.dx.describe_virtual_interfaces, "virtualInterfaces"):
            vifs[vif['virtualInterfaceId']] = {'virtualGatewayId': vif ['virtualGatewayId'], 'connectionId' : vif['connectionId']}
            if vif ['virtualGatewayId'] in vgws:
                vgws[vif['virtualGatewayId']]['vifs'].append(vif['virtualInterfaceId'])
                vgws[vif['virtualGatewayId']]['connections'].append(vif['connectionId'])
            else:
                vgws[vif['virtualGatewayId']]= {'vifs' : [vif['virtualInterfaceId']], 'connections' : [vif['connectionId']]}
        
        for vgw_id in vgws:
            finding_rec = self.get_vgw_output(vgw_id)
            if len(vgws[vgw_id]['vifs']) < 2:
                finding_rec['potential_single_az_risk'] = True
                finding_rec['message'] = f"Direct Connect: There is only one VIF {vgws[vgw_id]['vifs']} for the virtual gateway {vgw_id}."
            elif len(vgws[vgw_id]['connections']) < 2:
                finding_rec['potential_single_az_risk'] = True
                finding_rec['message'] = f"Direct Connect: Though there are more than 1 VIFs for the virtual gateway {vgw_id}, all the VIFs are on the same DX Connection {vgws[vgw_id]['connections']}."
            else:
                finding_rec['potential_single_az_risk'] = False
                finding_rec['message'] = f"Direct Connect: There are more than 1 VIFs for the virtual gateway {vgw_id}, and the VIFs are on more than one DX connection."

#Contains the logic to extract relevant fields from the API response to the output csv file.
    def get_dx_output(self):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = 'N/A'
        finding_rec['resource_name'] = 'N/A'
        finding_rec['resource_arn'] = 'N/A'
        return finding_rec 

    def get_vgw_output(self, vgw_id):

        finding_rec = self.get_finding_rec_with_common_fields()
        finding_rec['resource_id'] = vgw_id
        finding_rec['resource_name'] = 'N/A'
        finding_rec['resource_arn'] = 'N/A'
        return finding_rec 
