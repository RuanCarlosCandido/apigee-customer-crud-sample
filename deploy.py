#!/usr/bin/env python3

import base64
import getopt
import http.client
import json
import re
import os
import sys
import io
import urllib.parse
import zipfile
from google.oauth2 import service_account
from google.auth.transport.requests import Request


def httpCall(verb, uri, headers, body):
    if httpScheme == 'https':
        conn = http.client.HTTPSConnection(httpHost)
    else:
        conn = http.client.HTTPConnection(httpHost)

    if headers is None:
        hdrs = dict()
    else:
        hdrs = headers

    hdrs['Authorization'] = 'Bearer %s' % access_token
    conn.request(verb, uri, body, hdrs)

    return conn.getresponse()


def get_deployments():
    # Print info on deployments
    hdrs = {'Accept': 'application/json'}
    resp = httpCall('GET',
                    '/v1/organizations/%s/apis/%s/deployments' %
                    (Organization, Name),
                    hdrs, None)

    if resp.status != 200:
        return None

    return json.loads(resp.read())


def print_deployments(dep):
    for d in dep['environment']:
        print('Environment: %s' % d['name'])
        for r in d['revision']:
            print('  Revision: %s BasePath = %s' % (r['name'], r['configuration']['basePath']))
            print('  State: %s' % r['state'])
            if 'errors' in r:
                for e in r['errors']:
                    print('  Error: %s' % e['content'])


def path_contains_dot(p):
    c = re.compile(r'\.\w+')

    for pc in p.split('/'):
        if c.match(pc) is not None:
            return True

    return False


ApigeeHost = 'https://api.enterprise.apigee.com'
APIGEE_SERVICE_ACCOUNT_KEY = None
Directory = None
Organization = None
Environment = None
Name = None
BasePath = '/'
ShouldDeploy = True

Options = 'h:a:u:d:e:n:p:o:i:z:'

opts, args = getopt.getopt(sys.argv[1:], Options)

for o, v in opts:
    if o == '-n':
        Name = v
    elif o == '-o':
        Organization = v
    elif o == '-h':
        ApigeeHost = v
    elif o == '-a':
        ApigeeHost = v
    elif o == '-d':
        Directory = a
    elif o == '-e':
        Environment = a
    elif o == '-p':
        BasePath = a
    elif o == '-u':
        APIGEE_SERVICE_ACCOUNT_KEY = a
    elif o == '-i':
        ShouldDeploy = False
    elif o == '-z':
        ZipFile = a

if APIGEE_SERVICE_ACCOUNT_KEY is None or \
        (Directory is None and ZipFile is None) or \
        Environment is None or \
        Name is None or \
        Organization is None:
    print("""Usage: deploy.py -n [name] (-d [directory name] | -z [zipfile])
              -e [environment] -u [apigee_service_account_key] -o [organization]
              [-p [base path] -h [apigee API url] -i]
    base path defaults to "/"
    Apigee URL defaults to "https://api.enterprise.apigee.com"
    -i denotes to import only and not actually deploy
    """)
    sys.exit(1)

url = urllib.parse.urlparse(ApigeeHost)
httpScheme = url.scheme
httpHost = url.netloc

# Authenticate using the service account key
creds = service_account.Credentials.from_service_account_file(APIGEE_SERVICE_ACCOUNT_KEY, scopes=['https://www.googleapis.com/auth/cloud-platform'])
creds.refresh(Request())
access_token = creds.token

body = None

if Directory is not None:
    # Construct a ZIPped copy of the bundle in memory
    tf = io.BytesIO()
    zipout = zipfile.ZipFile(tf, 'w')

    dirList = os.walk(Directory)
    for dirEntry in dirList:
        if not path_contains_dot(dirEntry[0]):
            for fileEntry in dirEntry[2]:
                if not fileEntry.endswith('~'):
                    fn = os.path.join(dirEntry[0], fileEntry)
                    en = os.path.join(
                            os.path.relpath(dirEntry[0], Directory),
                            fileEntry)
                    print('Writing %s to %s' % (fn, en))
                    zipout.write(fn, en)

    zipout.close()
    body = tf.getvalue()
elif ZipFile is not None:
    with open(ZipFile, 'rb') as f:
        body = f.read()

# Upload the bundle to the API
hdrs = {'Content-Type': 'application/octet-stream',
        'Accept': 'application/json'}
uri = '/v1/organizations/%s/apis?action=import&name=%s' % \
            (Organization, Name)
resp = httpCall('POST', uri, hdrs, body)

if resp.status != 200 and resp.status != 201:
    print('Import failed to %s with status %i:\n%s' % \
            (uri, resp.status, resp.read()))
    sys.exit(2)

deployment = json.loads(resp.read())
revision = int(deployment['revision'])

print('Imported new proxy version %i' % revision)

if ShouldDeploy:
    # Undeploy duplicates
    deps = get_deployments()
    for env in deps['environment']:
        if env['name'] == Environment:
            for rev in env['revision']:
                if rev['configuration']['basePath'] == BasePath and int(rev['name']) != revision:
                    print('Undeploying revision %s in same environment and path:' % rev['name'])
                    resp = httpCall('POST',
                                    ('/v1/organizations/%s/apis/%s/revisions/%s/deployments' +
                                     '?action=undeploy' +
                                     '&env=%s') % \
                                    (Organization, Name, rev['name'], Environment),
                                    None, None)
                    if resp.status != 200 and resp.status != 204:
                        print('Error %i on undeployment:\n%s' % \
                                (resp.status, resp.read()))

    # Deploy the bundle
    hdrs = {'Accept': 'application/json'}
    resp = httpCall('POST',
        ('/v1/organizations/%s/apis/%s/revisions/%s/deployments' +
                '?action=deploy' +
                '&env=%s' +
                '&basepath=%s') % \
            (Organization, Name, revision, Environment, BasePath),
        hdrs, None)

    if resp.status != 200 and resp.status != 201:
        print('Deploy failed with status %i:\n%s' % (resp.status, resp.read()))
        sys.exit(2)

deps = get_deployments()
print_deployments(deps)

