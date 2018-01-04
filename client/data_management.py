import datetime
import json
import os
import re
from tempfile import mkstemp
import zipfile

from django.conf import settings

from api.serializers import (ScraperUserAgentSerializer, LandingPageSerializer,
                             RedirectPageSerializer, EmailTemplateSerializer)
from client.models import ScraperUserAgent, LandingPage, EmailTemplate


def zip_landing_pages(landing_pages, archive):
    ''' Add all file assets associated with landing_pages to an open archive.
    '''
    # Reference: http://stackoverflow.com/a/10480441
    for each_page in landing_pages:
        if not each_page.path:
            continue
        source_path = each_page.path
        # Get the start index of the page type directory in the path string.
        if source_path.find('landing-pages') != -1:
            path_cutting_index = source_path.find('landing-pages')
        else:
            path_cutting_index = source_path.find('redirect-pages')
        html_path_in_archive = source_path[path_cutting_index:]
        page_dir_path = os.path.dirname(os.path.dirname(html_path_in_archive))
        walk_dir = os.path.join(settings.MEDIA_ROOT, page_dir_path)
        for base, dirs, files in os.walk(walk_dir):
            for file in files:
                origin_path = os.path.join(base, file)
                each_file_relative_path_in_archive = os.path.join(*origin_path.split(os.path.sep)[-4:])
                archive.write(origin_path, each_file_relative_path_in_archive)


def unzip_landing_page_assets(landing_page_path, archive, old_dir, new_dir):
    ''' Unzip all assets associated with an archived LandingPage and update the
    links to those assets in its HTML to match the LandingPage's new location.

    old_dir and new_dir should be LandingPage directory names, such as:
    `/123-1496785023/`
    '''
    # Reference: http://stackoverflow.com/a/17729939
    archive_contents = archive.namelist()
    for archived_path in archive_contents:
        if archived_path.count(old_dir) > 0:
            new_path = os.path.join(settings.MEDIA_ROOT, archived_path.replace(old_dir, new_dir))
            if not os.path.exists(os.path.dirname(new_path)):
                os.makedirs(os.path.dirname(new_path))
            with open(new_path, 'w') as new_file:
                new_file.write(archive.read(archived_path))

    # After unpacking all the files, update the dirnames in the HTML file:
    with open(landing_page_path, 'rb') as html_file:
        cached_file = html_file.readlines()
        with open(landing_page_path, 'wb') as html_file:
            for each_line in cached_file:
                modified_line = re.sub(old_dir, new_dir, each_line)
                html_file.write(modified_line)


def zip_data_for_export(file_handle, scraper_user_agent_ids=list(), landing_page_ids=list(), redirect_page_ids=list(), email_template_ids=list()):
    data = dict()
    ids_of_pages_with_files_to_zip = list()

    if scraper_user_agent_ids:
        queryset = ScraperUserAgent.objects.filter(id__in=scraper_user_agent_ids)
        serializer = ScraperUserAgentSerializer(queryset, many=True)
        data['scraper_user_agents'] = serializer.data

    if landing_page_ids:
        queryset = LandingPage.objects.filter(id__in=landing_page_ids, is_redirect_page=False)

        for each_lp in queryset:
            if each_lp.path and os.path.exists(each_lp.path):
                ids_of_pages_with_files_to_zip.append(each_lp.id)

        serializer = LandingPageSerializer(queryset, many=True)
        data['landing_pages'] = serializer.data

    if redirect_page_ids:
        queryset = LandingPage.objects.filter(id__in=redirect_page_ids, is_redirect_page=True)

        for each_rp in queryset:
            if each_rp.path and os.path.exists(each_rp.path):
                ids_of_pages_with_files_to_zip.append(each_rp.id)

        serializer = LandingPageSerializer(queryset, many=True)
        data['redirect_pages'] = serializer.data

    if email_template_ids:
        queryset = EmailTemplate.objects.filter(id__in=email_template_ids)
        serializer = EmailTemplateSerializer(queryset, many=True)
        data['email_templates'] = serializer.data

    _, temp_json_path = mkstemp(suffix=".json")
    with open(temp_json_path, 'w') as datafile:
        datafile.write(json.dumps(data))

    # Reference: https://djangosnippets.org/snippets/365/
    with zipfile.ZipFile(file_handle, 'w', zipfile.ZIP_DEFLATED) as archive:
        if ids_of_pages_with_files_to_zip:
            landing_pages = LandingPage.objects.filter(id__in=ids_of_pages_with_files_to_zip)
            zip_landing_pages(landing_pages, archive)
        time_created = datetime.datetime.now().strftime('%s')
        archive.write(temp_json_path, 'data_{}.json'.format(time_created))

    return time_created


def load_data_from_zip_file(file_handle):
    messages = list()

    # Reference: https://pymotw.com/2/zipfile/
    archive_contents = file_handle.namelist()
    for each in archive_contents:
        if each.count('.json') > 0:
            json_filename = each
            break

    # Unpack the data file:
    json_data = file_handle.read(json_filename)
    data = json.loads(json_data)
    scraper_user_agents = data.get('scraper_user_agents', list())
    landing_pages = data.get('landing_pages', list())
    redirect_pages = data.get('redirect_pages', list())
    email_templates = data.get('email_templates', list())

    # Deserialize the data and unload the archive:
    landing_pages.extend(redirect_pages)
    table = sorted(landing_pages, key=lambda x: x['id'])
    for each_record in table:
        each_record.pop('id')
        old_path = each_record.pop('path')
        each_record['commit'] = True
        if each_record.get('is_redirect_page', False):
            serializer = RedirectPageSerializer(data=each_record)
        else:
            serializer = LandingPageSerializer(data=each_record)
        if serializer.is_valid():
            instance = serializer.save()
            if not old_path:
                continue
            now = datetime.datetime.now().strftime('%s')
            dir_pattern = r'(\/\d+-\d\d\d\d\d\d\d\d\d\d\/)'
            old_dirname = re.findall(dir_pattern, old_path)[0]
            new_dirname = '/{}-{}/'.format(instance.id, now)
            new_path = re.sub(dir_pattern, new_dirname, old_path)
            instance.path = new_path
            instance.save()

            try:
                unzip_landing_page_assets(new_path, file_handle, old_dirname, new_dirname)
            except Exception as error:
                page_type = 'Landing'
                if instance.is_redirect_page:
                    page_type = 'Redirect'
                error_message = ('{} Page #{} failed to import file assets: {}')
                messages.append(error_message.format(page_type, instance.id, error))

    for each_table in (scraper_user_agents, email_templates):
        each_table = sorted(each_table, key=lambda x: x['id'])
        # It's necessary to remove the IDs before deserializing the
        # records so that they're given new ones.
        for each_record in each_table:
            each_record.pop('id')
            each_record['commit'] = True

    serializer = ScraperUserAgentSerializer(data=scraper_user_agents, many=True)
    if serializer.is_valid():
        serializer.save()

    serializer = EmailTemplateSerializer(data=email_templates, many=True)
    if serializer.is_valid():
        serializer.save()

    return messages
