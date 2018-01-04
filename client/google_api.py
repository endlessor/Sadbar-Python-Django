# -*- coding: utf-8 -*-
from urllib import urlencode
import httplib2

from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest


def add_query_parameters(url, params):
    if not params:
        return url
    encoded = urlencode(params)
    if '?' in url:
        return '{}&{}'.format(url, encoded)
    else:
        return '{}?{}'.format(url, encoded)


def authorize_http(credentials):
    http = httplib2.Http()
    authed_http = credentials.authorize(http)
    if credentials.access_token_expired:
        credentials.refresh(authed_http)
    return authed_http


def execute_api_call(credentials, api_call):
    authed_http = authorize_http(credentials)
    return api_call.execute(http=authed_http)


# Gmail API
def messages_list(oauth_result, params=dict()):
    email = oauth_result.email
    credentials = oauth_result.credentials

    service = build('gmail', 'v1', http=httplib2.Http())
    users_resource = service.users()
    users_messages = users_resource.messages()
    api_call = users_messages.list(userId=email)

    api_call.uri = add_query_parameters(api_call.uri, params)

    return execute_api_call(credentials, api_call)


def messages_get(oauth_result, message_id, params=dict()):
    email = oauth_result.email
    credentials = oauth_result.credentials

    service = build('gmail', 'v1', http=httplib2.Http())
    users_resource = service.users()
    users_messages = users_resource.messages()
    api_call = users_messages.get(userId=email, id=message_id)

    api_call.uri = add_query_parameters(api_call.uri, params)

    return execute_api_call(credentials, api_call)


def batched_messages_get(oauth_result, message_ids, params=dict()):
    email = oauth_result.email
    credentials = oauth_result.credentials
    results_list = list()

    # Google's API client throws away the callback's return value inside
    # BatchHttpRequest._callback, during BatchHttpRequest.execute.
    # The solution, in this case, is to define the callback in the scope that
    # gives it access to the data structure we'll be returning the results in.
    def process_batch_responses(request_id, response, exception):
        if exception is not None:
            results_list.append(exception)
        else:
            results_list.append(response)

    batch = BatchHttpRequest()
    service = build('gmail', 'v1', http=httplib2.Http())
    users_resource = service.users()
    users_messages = users_resource.messages()

    for each_id in message_ids:
        api_call = users_messages.get(userId=email, id=each_id)
        api_call.uri = add_query_parameters(api_call.uri, params)
        batch.add(api_call, callback=process_batch_responses)

    execute_api_call(credentials, batch)
    return results_list


# GDrive API
def files_list(oauth_result, params=dict()):
    credentials = oauth_result.credentials
    service = build('drive', 'v3', http=httplib2.Http())
    files_resource = service.files()

    api_call = files_resource.list()
    api_call.uri = add_query_parameters(api_call.uri, params)
    return execute_api_call(credentials, api_call)


def files_get(oauth_result, file_id, params=dict()):
    credentials = oauth_result.credentials

    service = build('drive', 'v3', http=httplib2.Http())
    files_resource = service.files()

    api_call = files_resource.get(fileId=file_id)

    api_call.uri = add_query_parameters(api_call.uri, params)

    return execute_api_call(credentials, api_call)


def batched_files_get(oauth_result, file_ids, params=dict()):
    credentials = oauth_result.credentials
    results_list = list()

    # Google's API client throws away the callback's return value inside
    # BatchHttpRequest._callback, during BatchHttpRequest.execute.
    # The solution, in this case, is to define the callback in the scope that
    # gives it access to the data structure we'll be returning the results in.
    def process_batch_responses(request_id, response, exception):
        if exception is not None:
            results_list.append(exception)
        else:
            results_list.append(response)

    batch = BatchHttpRequest()
    service = build('drive', 'v3', http=httplib2.Http())
    files_resource = service.files()

    for each_id in file_ids:
        api_call = files_resource.get(fileId=each_id)
        api_call.uri = add_query_parameters(api_call.uri, params)
        batch.add(api_call, callback=process_batch_responses)

    execute_api_call(credentials, batch)
    return results_list


def files_get_media(oauth_result, file_id, params=dict()):
    credentials = oauth_result.credentials
    # This one requires authed_http because, unlike execute, get_media does not
    # update its http instance before we call the service. The error when an
    # authed Http instance is not used is "Daily limit exceeded"...
    authed_http = authorize_http(credentials)
    service = build('drive', 'v3', http=authed_http)
    files_resource = service.files()

    api_call = files_resource.get_media(fileId=file_id)

    api_call.uri = add_query_parameters(api_call.uri, params)
    # alt=media is necessary for indicating we want the file downloaded.
    api_call.headers.update({'alt': 'media'})

    # Unlike other Google API calls, this one must be executed on the other end
    # due to its very distinct extraction modes (whole vs chunked).
    # Using `execute_api_call` will return a string; use MediaIoBaseDownload to
    # treat it as a chunkable file.
    #     https://google.github.io/google-api-python-client/docs/epy/
    #                       googleapiclient.http.MediaIoBaseDownload-class.html
    return api_call
