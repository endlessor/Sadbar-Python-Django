from base64 import b64decode


def process_gmail_message_headers(message):
    headers = dict()

    # Convert all headers from a list to a JSON-compatible dict.
    try:
        for header in message['payload']['headers']:
            headers.update({header['name']: header['value']})
    except:
        pass

    # Verify the desired data is present, and provide a fallback if not.
    headers['Date'] = headers.get('Date', '(date missing)')
    headers['From'] = headers.get('From', '(sender missing)')
    headers['To'] = headers.get('To', '(recipients missing)')
    headers['Subject'] = headers.get('Subject', '(subject missing)')

    message['payload']['headers'] = headers

    return message


def process_gmail_message_body(message, requested_format):
    if 'parts' not in message['payload'].keys():
        message['payload']['parts'] = [{'body': dict()}]

    if requested_format == 'raw':
        undecoded = message.pop('raw')
        if undecoded is None:
            message['payload']['parts'][0]['body'].update({'data': '(body missing)'})
        else:
            decoded = b64decode(undecoded.replace('-', '+').replace('_', '/'))
            message['payload']['parts'][0]['body'].update({'data': decoded})

    elif requested_format == 'full':
        for index, each_part in enumerate(message['payload']['parts']):
            undecoded = message['payload']['parts'][index]['body'].get('data', None)
            if undecoded is None:
                message['payload']['parts'][index]['body'].update({'data': '(body missing)'})
            else:
                decoded = b64decode(undecoded.replace('-', '+').replace('_', '/'))
                message['payload']['parts'][index]['body'].update({'data': decoded})

    return message
