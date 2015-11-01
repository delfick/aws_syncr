from aws_syncr.amazon.common import AmazonMixin
from aws_syncr.errors import UnknownZone
from aws_syncr.differ import Differ

import boto3

import logging

log = logging.getLogger("aws_syncr.amazon.route53")

class Route53(AmazonMixin, object):
    def __init__(self, amazon, environment, accounts, dry_run):
        self.amazon = amazon
        self.dry_run = dry_run

        self.accounts = accounts
        self.account_id = accounts[environment]
        self.environment = environment

        self.client = self.amazon.session.client('route53')

    def route_info(self, route_name, zone):
        zones = self.client.list_hosted_zones_by_name(DNSName=zone)
        if not zones.get("HostedZones"):
            raise UnknownZone(zone=zone)

        info = {"zoneid": zones['HostedZones'][0]['Id'], 'zone': zone}

        next_record_name = ""
        next_record_type = ""
        next_record_identifier = ""
        while True:
            next_values = (("StartRecordName", next_record_name), ("StartRecordType", next_record_type), ("StartRecordIdentifier", next_record_identifier))
            kwargs = dict((name, val) for name, val in next_values if val)
            record_infos = self.client.list_resource_record_sets(HostedZoneId=info['zoneid'], **kwargs)

            for i in record_infos['ResourceRecordSets']:
                if i['Name'] == "{0}.{1}".format(route_name, zone):
                    info['record'] = i
                    return info

            if record_infos['IsTruncated']:
                next_record_name = record_infos['NextRecordName']
                next_record_type = record_infos['NextRecordType']
                next_record_identitifer = record_infos['NextRecordIdentifier']
            else:
                break

        # Didn't find the record
        return {}

    def create_route(self, name, zone, record_type, record_target):
        old = {}
        new = {"target": [{"Value": record_target}], 'type': record_type}
        changes = list(Differ.compare_two_documents(old, new))

        with self.catch_boto_400("Couldn't add record", record=name, zone=zone):
            for _ in self.change("+", "record", reocrd=name, zone=zone, changes=changes):
                pass

    def modify_route(self, route_info, name, zone, record_type, record_target):
        old = {"target": route_info['record']['ResourceRecords'], "type": route_info['record']['Type']}
        new = {"target": [{"Value": record_target}], 'type': record_type}
        changes = list(Differ.compare_two_documents(old, new))

        if changes:
            with self.catch_boto_400("Couldn't change record", record=name, zone=zone):
                for _ in self.change("M", "record", reocrd=name, zone=zone, changes=changes):
                    pass

