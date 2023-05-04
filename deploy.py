import argparse
import json
import os
import requests
from google.oauth2 import service_account

def get_access_token(service_account_key):
    credentials = service_account.Credentials.from_service_account_info(service_account_key)
    scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/cloud-platform'])
    access_token = scoped_credentials.get_access_token().access_token
    return access_token

def deploy_proxy(proxy_name, org_name, host, directory, environment, service_account_key):
    access_token = get_access_token(service_account_key)
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/octet-stream'
    }

    url = f'{host}/v1/organizations/{org_name}/apis?action=import&name={proxy_name}'

    with open(f'{directory}/apiproxy/{proxy_name}.zip', 'rb') as f:
        response = requests.post(url, headers=headers, data=f)

    if response.status_code != 201:
        print(f'Import failed with status {response.status_code}:\n{response.text}')
        return

    revision = response.json()['revision']
    url = f'{host}/v1/organizations/{org_name}/environments/{environment}/apis/{proxy_name}/revisions/{revision}/deployments'

    response = requests.post(url, headers=headers)

    if response.status_code != 200:
        print(f'Deployment failed with status {response.status_code}:\n{response.text}')
    else:
        print(f'Successfully deployed revision {revision} to {environment} environment.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Deploy an Apigee proxy')
    parser.add_argument('-n', '--name', required=True, help='Proxy name')
    parser.add_argument('-o', '--org', required=True, help='Apigee organization')
    parser.add_argument('-a', '--host', required=True, help='Apigee API host')  # Change this line
    parser.add_argument('-d', '--directory', required=True, help='Proxy directory')
    parser.add_argument('-e', '--env', required=True, help='Apigee environment')
    parser.add_argument('-k', '--key', required=True, help='Apigee service account key (JSON string)')
    args = parser.parse_args()

    service_account_key = json.loads(args.key)
    deploy_proxy(args.name, args.org, args.host, args.directory, args.env, service_account_key)
