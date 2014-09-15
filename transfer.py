#!/usr/bin/python

import httplib2
import apiclient.discovery
import apiclient.http
import apiclient.errors
import oauth2client.client
import sys
import pprint
import os

def get_drive_service():
    OAUTH2_SCOPE = 'https://www.googleapis.com/auth/drive'
    CLIENT_SECRETS = 'client_secrets.json'
    flow = oauth2client.client.flow_from_clientsecrets(CLIENT_SECRETS, OAUTH2_SCOPE)
    flow.redirect_uri = oauth2client.client.OOB_CALLBACK_URN
    authorize_url = flow.step1_get_authorize_url()
    print('Use this link for authorization: {}'.format(authorize_url))
    code = raw_input('Verification code: ').strip()
    credentials = flow.step2_exchange(code)
    http = httplib2.Http()
    credentials.authorize(http)
    drive_service = apiclient.discovery.build('drive', 'v2', http=http)
    return drive_service

def get_permission_id_for_email(service, email):
    try:
        id_resp = service.permissions().getIdForEmail(email=email).execute()
        return id_resp['id']
    except apiclient.errors.HttpError as e:
        print('An error occured: {}'.format(e))

def show_info(service, drive_item, prefix, permission_id):
    try:
        print(os.path.join(prefix, drive_item['title']))
        print('Would set new owner to {}.'.format(permission_id))
    except KeyError:
        print('No title for this item:')
        pprint.pprint(drive_item)

def grant_ownership(service, drive_item, prefix, permission_id):
    full_path = os.path.join(prefix, drive_item['title'])

    pprint.pprint(drive_item)

    current_user_owns = False
    for owner in drive_item['owners']:
        if owner['permissionId'] == permission_id:
            print('Item {} already has the right owner.'.format(full_path))
            return
        elif owner['isAuthenticatedUser']:
            current_user_owns = True

    print('Item {} needs updated permissions.'.format(full_path))

    if not current_user_owns:
        print('    But, current user does not own the item.'.format(full_path))
        return

    try:
        permission = service.permissions().get(fileId=drive_item['id'], permissionId=permission_id).execute()
        permission['role'] = 'owner'
        return service.permissions().update(fileId=drive_item['id'], permissionId=permission_id, body=permission, transferOwnership=True).execute()
    except apiclient.errors.HttpError as e:
        if e.resp.status == 404:
            print('    But, new owner needs some permissions before being granted ownership.')
        else:
            print('An error occurred: {}'.format(e))

def process_all_files(service, callback=None, callback_args=None, minimum_prefix='', current_prefix='', folder_id='root'):
    print('Gathing file listings for prefix {}...'.format(current_prefix))

    if callback_args is None:
        callback_args = []

    page_token = None
    while True:
        try:
            param = {}
            if page_token:
                param['pageToken'] = page_token
            children = service.children().list(folderId=folder_id, **param).execute()
            for child in children.get('items', []):
                item = service.files().get(fileId=child['id']).execute()
                #pprint.pprint(item)
                if item['kind'] == 'drive#file':
                    if item['mimeType'] == 'application/vnd.google-apps.folder':
                        print('Folder: {} ({}, {})'.format(item['title'], current_prefix, item['id']))
                        next_prefix = os.path.join(current_prefix, item['title'])
                        comparison_length = min(len(next_prefix), len(minimum_prefix))
                        if minimum_prefix[:comparison_length] == next_prefix[:comparison_length]:
                            process_all_files(service, callback, callback_args, minimum_prefix, next_prefix, item['id'])
                    elif current_prefix.startswith(minimum_prefix):
                        print('File: {} ({}, {})'.format(item['title'], current_prefix, item['id']))
                        if current_prefix.startswith(minimum_prefix):
                            callback(service, item, current_prefix, **callback_args)
            page_token = children.get('nextPageToken')
            if not page_token:
                break
        except apiclient.errors.HttpError as e:
            print('An error occurred: {}'.format(e))
            break

if __name__ == '__main__':
    minimum_prefix = sys.argv[1]
    new_owner = sys.argv[2]
    print('Changing all files at path "{}" to owner "{}"'.format(minimum_prefix, new_owner))
    service = get_drive_service()
    permission_id = get_permission_id_for_email(service, new_owner)
    print('User {} is permission ID {}.'.format(new_owner, permission_id))
    process_all_files(service, grant_ownership, {'permission_id': permission_id}, minimum_prefix)
    #print(files)