#!/usr/bin/python3.11

import argparse
import logging
import os

from modules import create_signer
from modules import TagUpdater

ENV_NAMESPACE = 'OCI_TAG_NAMESPACE'
ENV_KEY = 'OCI_TAG_KEY'

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument('-n', '--namespace', required=True, help='Tag namespace to update')
parser.add_argument('-k', '--key', required=True, help='Key to change in tag namespace')
parser.add_argument('-c', '--compartments', default=None,
        help='Comma seperated list of compartment OCIDs to check for tag updates or root if empty')
parser.add_argument('-p', '--profile', default=None, help='OCI Profile name to use')
parser.add_argument('--auth',
    default='profile',
    choices=[
        'profile',
        'instance_principal',
        'resource_principal'
])
args = parser.parse_args()

# Check environment variables if no args given
namespace = args.namespace if args.namespace else os.getenv(ENV_NAMESPACE)
key = args.key if args.key else os.getenv(ENV_KEY)

#config = {}
#signer = None

if args.auth == 'profile':
    config, signer = create_signer(args.profile)
elif args.auth == 'instance_principal':
    config, signer = create_signer(None, instance_principal=True)
elif args.auth == 'resource_principal':
    config, signer = create_signer(None, delegation_token=True)
log.debug(f'Config: {config}\n\tSigner: {signer}')

# Compartments needs to be a list of OCIDs whether provided or not
compartments = args.compartments.split(',') if args.compartments else [config['tenancy']]

log.info(f'Updating tag default {args.namespace}.{args.key} in compartment(s) {compartments}')

tc = TagUpdater(config, compartments, signer=signer)
tc.update_tags(args.namespace, args.key)
