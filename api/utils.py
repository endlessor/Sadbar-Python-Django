import pytz
import csv
import re
import logging

from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework_jwt.settings import api_settings

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError

from client.models import Client, Target


logger = logging.getLogger(__name__)


def jwt_response_payload_handler(token, user=None, request=None):
    response = {
        'token': token
    }

    if user is None:
        response['user'] = None
    else:
        response['user'] = {
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'email': user.email,
            'id': user.id
        }

    try:
        response['user']['profile'] = {
            'id': user.profile.id,
            'timezone': user.profile.timezone
        }
    except User.profile.RelatedObjectDoesNotExist:
        response['user']['profile'] = None

    return response


def make_jwt_for_user(user):
    payload = api_settings.JWT_PAYLOAD_HANDLER(user)
    token = api_settings.JWT_ENCODE_HANDLER(payload)
    return token


def normalize_timezone(timezone):
    return timezone.lower().replace('/', '').replace('_', '').replace(' ', '')


def clean_timezone(input_timezone):
    normalized_input = normalize_timezone(input_timezone)
    normalized_pytzs = map(normalize_timezone, pytz.all_timezones)
    timezone_map = zip(normalized_pytzs, pytz.all_timezones)
    timezone_dict = dict(timezone_map)
    found_timezone = timezone_dict.get(normalized_input, None)

    if found_timezone is None:
        raise DRFValidationError(
            {'timezone': ['Invalid timezone: "{}"'.format(input_timezone)]}
        )

    return found_timezone


def convert_validation_error(django_validation_error):
    """
    Convert a Django.core.exceptions.ValidationError into a
    rest_framework.exceptions.ValidationError and return it.
    """
    # Reference: https://github.com/
    #      tomchristie/django-rest-framework/issues/2145#issuecomment-151081104
    errors = dict()
    for each_field in django_validation_error:
        errors.update({each_field[0]: each_field[1]})
    return DRFValidationError(errors)


def separate_target_fields_from_data(target_data):
    target_field_values = dict()

    timezone = target_data.get('timezone', '')
    # Check falsiness to catch null values, not just KeyErrors.
    if timezone:
        target_data.pop('timezone')

    target_field_values['timezone'] = timezone

    for each in ('email', 'lastname', 'firstname'):
        try:
            target_field_values[each] = target_data.pop(each)
        except KeyError:
            pass

    return (target_field_values, target_data)


def fix_csv_fieldnames(fieldnames):
    fixed_fieldnames = list()

    for each_fieldname in fieldnames:
        shortcodified_fieldname = re.sub('\W+', '', each_fieldname)
        # Target-field shortcodes must be fully lowercase.
        if shortcodified_fieldname.lower() == 'email':
            fixed_fieldnames.append('email')
        elif shortcodified_fieldname.lower() == 'firstname':
            fixed_fieldnames.append('firstname')
        elif shortcodified_fieldname.lower() == 'lastname':
            fixed_fieldnames.append('lastname')
        elif shortcodified_fieldname.lower() == 'timezone':
            fixed_fieldnames.append('timezone')
        else:
            fixed_fieldnames.append(shortcodified_fieldname)

    return fixed_fieldnames


def extract_targets_and_data_from_csv(csv_file):
    decoded_csv_lines = list()
    prospective_targets = list()

    csv_file.seek(0)
    csv_lines = csv_file.readlines()
    for index, each_line in enumerate(csv_lines):
        try:
            decoded_csv_lines.append(each_line.decode('utf-8'))
        except:
            logger.info('[ ! ] Non-UTF8 character encountered on line {} of'
                        ' uploaded CSV'.format(index))
            decoded_csv_lines.append(each_line.decode('utf-8', 'ignore'))

    reader = csv.DictReader(decoded_csv_lines)
    reader.fieldnames = fix_csv_fieldnames(reader.fieldnames)

    for each_line in reader:
        prospective_targets.append(separate_target_fields_from_data(each_line))

    return prospective_targets


def create_target_list_from_csv(csv_file, filename):
    """
    From an opened csv_file, return an unsaved, flattened representation of
    a populated TargetList using filename as the TargetList's nickname, with no
    client and an empty description.
    """
    target_list = {
        'nickname': filename,
        'description': '',
        'client': None,
        'target': list()
    }

    prospective_targets = extract_targets_and_data_from_csv(csv_file)

    for target_field_values, extra_target_data in prospective_targets:

        target = {'timezone': target_field_values['timezone']}

        email = target_field_values.get('email', None)
        firstname = target_field_values.get('firstname', None)
        lastname = target_field_values.get('lastname', None)

        if email is not None:
            target['email'] = email
        if firstname is not None:
            target['firstname'] = firstname
        if lastname is not None:
            target['lastname'] = lastname

        for label, value in extra_target_data.iteritems():
            target[label] = value

        target_list['target'].append(target)

    return target_list


def retrieve_target_from_mixed_data(mixed_data):
    """
    Extract and validate target data from a mixed_data single-target dict.

    If any columns or Target field data are missing, raise a ValidationError
    indicating the column and, if possible, the ID of the affected Target.

    Return a tuple of an unsaved Target and the original dict with all Target
    fields removed.
    """
    try:
        email = mixed_data.pop('email')
        firstname = mixed_data.pop('firstname')
        lastname = mixed_data.pop('lastname')
    except KeyError as error:
        raise DRFValidationError(
            {'target': {error.message: 'This column is required.'}}
        )

    # ID can be absent if this is a new Target.
    target_id = mixed_data.get('id', None)
    if 'id' in mixed_data.keys():
        mixed_data.pop('id')

    # In addition to the basic model field validation, ensure required fields
    # aren't empty.
    if not email:
        raise DRFValidationError(
            {'target': {'id': target_id,
                        'email': 'This field is required.'}}
        )
    if not firstname:
        raise DRFValidationError(
            {'target': {'id': target_id,
                        'firstname': 'This field is required.'}}
        )
    if not lastname:
        raise DRFValidationError(
            {'target': {'id': target_id,
                        'lastname': 'This field is required.'}}
        )

    timezone = mixed_data.get('timezone', Client.INVALID_TIMEZONE)
    if 'timezone' in mixed_data.keys():
        mixed_data.pop('timezone')

    if target_id is not None:
        try:
            target = Target.objects.get(id=target_id)
        except Target.DoesNotExist:
            raise DRFValidationError({'target': 'Target with ID {} not found.'
                                                ''.format(target_id)})
        target.email = email
        target.firstname = firstname
        target.lastname = lastname
        # By using an invalid timezone, we can allow timezones to be either
        # nulled or converted to their Target's existing value depending on
        # whether or not the Target already exists.
        if timezone == Client.INVALID_TIMEZONE:
            target.timezone = target.timezone
        else:
            target.timezone = timezone
    else:
        if timezone == Client.INVALID_TIMEZONE:
            timezone = None
        target = Target(email=email,
                        firstname=firstname,
                        lastname=lastname,
                        timezone=timezone)

    try:
        target.clean_fields()
    except DjangoValidationError as django_validation_error:
        # Similar to convert_validation_error, but with additional
        # formatting and data about the specific Target affected.
        errors = {'target': {'id': target_id}}
        for each_field in django_validation_error:
            errors['target'].update({each_field[0]: each_field[1][0]})
        raise DRFValidationError(errors)

    return target, mixed_data


def decode_quopri(template):
    try:
        decoded_template = template.encode('ascii', 'ignore').\
                                    decode('quopri')
        return {'success': True, 'template': decoded_template, 'error': None}
    except UnicodeDecodeError as error:
        error_message = ('Unable to decode email template: Template is not'
                         ' quoted printable-encoded.')
        logger.info('[ ! ] {}\n    error: {}'.format(error_message, error))
        return {'success': False, 'template': None, 'error': error_message}
    except Exception as error:
        error_message = ('Unable to decode email template due to an'
                         ' internal error: {}'.format(error))
        logger.info('[ ! ] {}\n    error: {}'.format(error_message, error))
        return {'success': False, 'template': None, 'error': error_message}
