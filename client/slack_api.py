import json
import logging
import requests
import sys


logger = logging.getLogger(__name__)


def send_slack_message(channel, username, icon_emoji, text, slack_hook):
    try:
        if 'test' in sys.argv:
            logger.debug('[ . ] Blocked Slack message: test conditions active.')
            return

        response = requests.post(slack_hook.webhook_url,
                                 data=json.dumps({'channel': channel,
                                                  'username': username,
                                                  'icon_emoji': icon_emoji,
                                                  'text': text}),
                                 headers={'Content-Type': 'application/json'})

        if response.status_code != 200:
            warning = '[ ! ] Slack hook returned status code {}: {}'
            logger.warn(warning.format(response.status_code, response.text))

    except Exception as e:
        logger.warn('[ ! ] Error attempting to send Slack message: {}'.format(e))
