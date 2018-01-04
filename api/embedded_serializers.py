# -*- coding: utf-8 -*-
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.exceptions import APIException
from rest_framework import serializers, status

from dynamic_rest.fields import (DynamicRelationField, DynamicComputedField,
                                 DynamicMethodField)
from dynamic_rest.serializers import (DynamicModelSerializer, EphemeralObject,
                                      DynamicEphemeralSerializer)

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone as dj_tz

from client.models import *
from api.utils import clean_timezone, convert_validation_error


class EmbeddedSiteSettingsSerializer(DynamicModelSerializer):
    public_ip = serializers.IPAddressField(required=False)

    commit = serializers.BooleanField(default=False, write_only=True)
    server_time = DynamicMethodField()
    server_timezone = DynamicMethodField()

    class Meta:
        model = SiteSettings
        fields = ('id', 'public_ip', 'commit', 'server_time',
                  'server_timezone')
        read_only_fields = ('id', 'server_time', 'server_timezone')

    def get_server_time(self, instance):
        return dj_tz.now()

    def get_server_timezone(self, instance):
        return str(settings.TIME_ZONE)

    def create(self, validated_data):
        commit = validated_data.pop('commit')

        if SiteSettings.objects.exists():
            ss_id = SiteSettings.objects.first().id
            raise DRFValidationError({'non_field_errors': ['Site Settings'
                                                           ' object already'
                                                           ' exists: ID {}'
                                                           ''.format(ss_id)]})
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.public_ip = validated_data.get('public_ip',
                                                instance.public_ip)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedSlackHookSerializer(DynamicModelSerializer):
    webhook_url = serializers.CharField(max_length=1000, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = SlackHook
        fields = ('id', 'webhook_url', 'description', 'commit')
        read_only_fields = ('id', )

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.webhook_url = validated_data.get('webhook_url',
                                                  instance.webhook_url)
        instance.description = validated_data.get('description',
                                                  instance.description)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


# User endpoint reference:
#     https://richardtier.com/2014/02/25/django-rest-framework-user-endpoint/
class EmbeddedUserSerializer(DynamicModelSerializer):
    # "You can add extra fields to a ModelSerializer or override the default
    #      fields by declaring fields on the class, just as you would for a
    #      Serializer class."
    # If you have a field specified here, the Meta for it will be ignored;
    # of note is write_only for password, which can also be a Meta attribute.
    # Reference: http://stackoverflow.com/a/38327741
    username = serializers.CharField(max_length=30, required=True)
    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(max_length=30, required=False)
    last_name = serializers.CharField(max_length=30, required=False)
    password = serializers.CharField(max_length=128, required=False,
                                     write_only=True)
    # Reference: http://stackoverflow.com/a/27591289
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'first_name',
                  'last_name', 'is_active', 'commit')
        read_only_fields = ('id', 'is_active')

    # Reference: http://www.django-rest-framework.org/
    #                                   api-guide/serializers/#saving-instances
    # "Calling .save() will either create a new instance, or update an existing
    # instance, depending on if an existing instance was passed when
    # instantiating the serializer class."
    def create(self, validated_data):
        commit = validated_data.pop('commit')

        # Catch Django model field ValidationErrors and convert them into
        # Django REST framework serializer field ValidationErrors:
        try:
            instance = self.Meta.model(**validated_data)
            # The password field is required on create but not on update.
            # This is incorporated into the Django model field validators, so
            # calling Model.clean_fields will raise a Django ValidationError.
            instance.clean_fields()
            # set_password ensures Django hashes the password before saving it.
            # Call this after clean_fields to first ensure a password exists.
            instance.set_password(validated_data.get('password'))
        # Django ValidationErrors don't create the right DRF API responses when
        # raised; converting it to a rest_framework ValidationError fixes this:
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        # User.set_password tells Django to hash the password before saving it.
        instance.set_password(validated_data.get('password',
                                                 instance.password))
        instance.first_name = validated_data.get('first_name',
                                                 instance.first_name)
        instance.last_name = validated_data.get('last_name',
                                                instance.last_name)
        instance.is_active = validated_data.get('is_active',
                                                instance.is_active)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedProfileSerializer(DynamicModelSerializer):
    user = DynamicRelationField('EmbeddedUserSerializer', required=True, embed=True)
    timezone = serializers.CharField(allow_null=True, allow_blank=True,
                                     required=False)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Profile
        fields = ('id', 'user', 'timezone', 'commit')
        read_only_fields = ('id',)

    def validate(self, data):
        if self.instance is None:
            user = data.get('user')
            timezone = data.get('timezone')
        else:
            user = data.get('user', self.instance.user)
            timezone = data.get('timezone', self.instance.timezone)

        if not hasattr(user, 'profile'):
            pass
        elif not hasattr(self.instance, 'id') or user.profile.id != self.instance.id:
            raise DRFValidationError({'user': ['User {} already has a profile: {}'
                                               ''.format(user.id, user.profile.id)]})
        if timezone:
            data.update({'timezone': clean_timezone(timezone)})

        return data

    def create(self, validated_data):
        commit = validated_data.pop('commit')

        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.user = validated_data.get('user', instance.user)
        instance.timezone = validated_data.get('timezone', instance.timezone)

        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedEmailServerSerializer(DynamicModelSerializer):
    host = serializers.CharField(max_length=100, required=True)
    port = serializers.IntegerField(required=True)
    use_tls = serializers.BooleanField(required=False)
    login = serializers.EmailField(max_length=100, required=True)
    password = serializers.CharField(max_length=100, required=True,
                                     label='Account Password')
    test_recipient = serializers.EmailField(required=False,
                                            label='Test this configuration:')
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = EmailServer
        fields = ('id', 'host', 'port', 'use_tls', 'login', 'password',
                  'test_recipient', 'commit')
        read_only_fields = ('id',)

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.host = validated_data.get('host', instance.host)
        instance.port = validated_data.get('port', instance.port)
        instance.use_tls = validated_data.get('use_tls', instance.use_tls)
        instance.login = validated_data.get('login', instance.login)
        instance.password = validated_data.get('password', instance.password)
        instance.test_recipient = validated_data.get('test_recipient',
                                                     instance.test_recipient)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedPhishingDomainSerializer(DynamicModelSerializer):
    protocol = serializers.ChoiceField(choices=PhishingDomain.PROTOCOLS,
                                       required=True)
    domain_name = serializers.CharField(max_length=100, required=True)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = PhishingDomain
        fields = ('id', 'protocol', 'domain_name', 'commit')
        read_only_fields = ('id',)

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.protocol = validated_data.get('protocol', instance.protocol)
        instance.domain_name = validated_data.get('domain_name',
                                                  instance.domain_name)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedScraperUserAgentSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=100, required=True)
    user_agent_data = serializers.CharField(allow_blank=True, required=False)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = ScraperUserAgent
        fields = ('id', 'name', 'user_agent_data', 'commit')
        read_only_fields = ('id',)

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.user_agent_data = validated_data.get('user_agent_data',
                                                      instance.user_agent_data)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedScheduleSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    is_default = serializers.BooleanField(default=True)
    interval = serializers.IntegerField(required=False, min_value=10)
    excluded_dates = serializers.ListField(
        child=serializers.DateField(required=False, default=''),
        required=False,
        default=list
    )
    commit = serializers.BooleanField(write_only=True)

    class Meta:
        model = Schedule
        fields = ('id', 'name', 'description', 'is_default', 'interval',
                  'excluded_dates', 'commit')
        read_only_fields = ('id', )

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description',
                                                  instance.description)
        instance.is_default = validated_data.get('is_default',
                                                 instance.is_default)
        instance.interval = validated_data.get('interval',
                                               instance.interval)
        instance.excluded_dates = validated_data.get('excluded_dates',
                                                     instance.excluded_dates)

        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedScheduleWindowSerializer(DynamicModelSerializer):
    schedule = DynamicRelationField('EmbeddedScheduleSerializer', embed=True, required=True)
    day_of_the_week = serializers.CharField(required=False)
    open_time = serializers.TimeField(required=False)
    close_time = serializers.TimeField(required=False)
    commit = serializers.BooleanField(write_only=True)

    class Meta:
        model = ScheduleWindow
        fields = ('id', 'schedule', 'day_of_the_week', 'open_time',
                  'close_time', 'commit')
        read_only_fields = ('id', )

    def create(self, validated_data):
        commit = validated_data.pop('commit')

        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.schedule = validated_data.get('schedule',
                                               instance.schedule)
        instance.day_of_the_week = validated_data.get('day_of_the_week',
                                                      instance.day_of_the_week)
        instance.open_time = validated_data.get('open_time',
                                                instance.open_time)
        instance.close_time = validated_data.get('close_time',
                                                 instance.close_time)

        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedLandingPageSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=100, required=True)
    description = serializers.CharField(allow_blank=True, required=False)
    url = serializers.CharField(max_length=1000, required=False,
                                allow_null=True, allow_blank=True)
    path = serializers.CharField(max_length=255, required=False)
    is_redirect_page = serializers.BooleanField(default=False)
    status = serializers.IntegerField(required=False)
    page_type = serializers.CharField(max_length=10, required=True)
    scraper_user_agent = DynamicRelationField('EmbeddedScraperUserAgentSerializer', embed=True,
                                              required=True, allow_null=True)
    date_created = serializers.DateTimeField(required=False)
    source = serializers.CharField(required=False, allow_blank=True,
                                   write_only=True)
    refetch = serializers.BooleanField(required=False, write_only=True)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = LandingPage
        fields = ('id', 'name', 'description', 'url', 'path',
                  'is_redirect_page', 'status', 'page_type',
                  'scraper_user_agent', 'date_created', 'source', 'refetch',
                  'commit')
        read_only_fields = ('id', 'path', 'is_redirect_page', 'date_created')

    def create(self, validated_data):
        commit = validated_data.pop('commit')

        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description',
                                                  instance.description)
        instance.url = validated_data.get('url', instance.url)
        instance.status = validated_data.get('status', instance.status)
        instance.page_type = validated_data.get('page_type',
                                                instance.page_type)
        instance.scraper_user_agent = validated_data.get('scraper_user_agent',
                                                   instance.scraper_user_agent)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedRedirectPageSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=100, required=True)
    description = serializers.CharField(required=False)
    url = serializers.CharField(max_length=1000, required=False,
                                allow_null=True, allow_blank=True)
    path = serializers.CharField(max_length=255, required=False)
    is_redirect_page = serializers.BooleanField(default=True)
    status = serializers.IntegerField(required=False)
    page_type = serializers.CharField(max_length=10, required=True)
    scraper_user_agent = DynamicRelationField('EmbeddedScraperUserAgentSerializer', embed=True,
                                              required=True, allow_null=True)
    date_created = serializers.DateTimeField(required=False)
    source = serializers.CharField(required=False, allow_blank=True,
                                   write_only=True)
    refetch = serializers.BooleanField(required=False, write_only=True)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = LandingPage
        fields = ('id', 'name', 'description', 'url', 'path',
                  'is_redirect_page', 'status', 'page_type',
                  'scraper_user_agent', 'date_created', 'source', 'refetch',
                  'commit')
        read_only_fields = ('id', 'path', 'is_redirect_page', 'date_created')

    def create(self, validated_data):
        commit = validated_data.pop('commit')

        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description',
                                                  instance.description)
        instance.url = validated_data.get('url', instance.url)
        instance.status = validated_data.get('status', instance.status)
        instance.page_type = validated_data.get('page_type',
                                                instance.page_type)
        instance.scraper_user_agent = validated_data.get('scraper_user_agent',
                                                   instance.scraper_user_agent)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedEmailTemplateSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=100, required=True,
                                 label='Template Name')
    description = serializers.CharField(required=False, label='Description')
    from_header = serializers.CharField(max_length=100, required=True,
                                        label='From Header')
    subject_header = serializers.CharField(max_length=100, required=True,
                                           label='Subject')
    template = serializers.CharField(required=False)
    decode = serializers.BooleanField(default=False, write_only=True)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = EmailTemplate
        fields = ('id', 'name', 'description', 'from_header', 'subject_header',
                  'template', 'decode', 'commit')
        read_only_fields = ('id',)

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            validated_data.pop('decode')
        except KeyError:
            pass

        template = validated_data['template']
        template = template.replace('http://[url]', '[url]').\
                            replace('https://[url]', '[url]').\
                            replace('ftp://[url]', '[url]').\
                            replace('news://[url]', '[url]')
        validated_data.update({'template': template})

        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        try:
            validated_data.pop('decode')
        except KeyError:
            pass

        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description',
                                                  instance.description)
        instance.from_header = validated_data.get('from_header',
                                                  instance.from_header)
        instance.subject_header = validated_data.get('subject_header',
                                                     instance.subject_header)
        template = validated_data.get('template', instance.template)
        template = template.replace('http://[url]', '[url]').\
                            replace('https://[url]', '[url]').\
                            replace('ftp://[url]', '[url]').\
                            replace('news://[url]', '[url]')
        instance.template = template

        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedClientSerializer(DynamicModelSerializer):
    url = serializers.URLField(max_length=100, required=True, label='URL')
    default_time_zone = serializers.CharField(required=True,
                                              initial='Etc/GMT+7')
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Client
        fields = ('id', 'name', 'url', 'default_time_zone', 'commit')
        read_only_fields = ('id',)

    def validate(self, data):
        if self.instance is None:
            default_time_zone = data.get('default_time_zone')
        else:
            default_time_zone = data.get('default_time_zone',
                                         self.instance.default_time_zone)
        if default_time_zone:
            data.update({'default_time_zone': clean_timezone(default_time_zone)})

        return data

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.url = validated_data.get('url', instance.url)
        instance.default_time_zone = validated_data.get('default_time_zone',
                                                    instance.default_time_zone)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedCampaignSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=100, required=True, label='Title')
    description = serializers.CharField(allow_blank=True, required=False)
    client = DynamicRelationField('EmbeddedClientSerializer', embed=True, required=False)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Campaign
        fields = ('id', 'name', 'description', 'client', 'commit')
        read_only_fields = ('id',)

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description',
                                                  instance.description)
        instance.client = validated_data.get('client', instance.client)

        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedResultEventSerializer(DynamicModelSerializer):
    vector_email = DynamicRelationField('EmbeddedVectorEmailSerializer',
                                        deferred=True, many=True, embed=True)

    class Meta:
        model = ResultEvent
        fields = ('id', 'event_type', 'timestamp', 'userAgent', 'ip', 'login',
                  'password', 'raw_data', 'vector_email')
        read_only_fields = ('id', 'event_type', 'timestamp', 'userAgent', 'ip',
                            'login', 'password', 'raw_data', 'vector_email')


class EmbeddedTargetDatumSerializer(DynamicModelSerializer):
    target_list = DynamicRelationField('EmbeddedTargetListSerializer', required=True, embed=True)
    target = DynamicRelationField('EmbeddedTargetSerializer', required=True, embed=True)
    label = serializers.CharField(max_length=100, required=True)
    value = serializers.CharField(allow_blank=True, required=False)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = TargetDatum
        fields = ('id', 'target_list', 'target', 'label', 'value', 'commit')
        read_only_fields = ('id',)

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.target_list = validated_data.get('target_list',
                                                  instance.target_list)
        instance.target = validated_data.get('target', instance.target)
        instance.label = validated_data.get('label', instance.label)
        instance.value = validated_data.get('value', instance.value)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedTargetSerializer(DynamicModelSerializer):
    email = serializers.EmailField(required=True)
    firstname = serializers.CharField(max_length=50, required=False)
    lastname = serializers.CharField(max_length=50, required=False)
    timezone = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Target
        fields = ('id', 'email', 'firstname', 'lastname', 'timezone', 'commit')
        read_only_fields = ('id',)

    def validate(self, data):
        if self.instance is None:
            timezone = data.get('timezone')
        else:
            timezone = data.get('timezone', self.instance.timezone)

        if timezone:
            data.update({'timezone': clean_timezone(timezone)})

        return data

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.email = validated_data.get('email', instance.email)
        instance.firstname = validated_data.get('firstname',
                                                instance.firstname)
        instance.lastname = validated_data.get('lastname', instance.lastname)
        instance.timezone = validated_data.get('timezone', instance.timezone)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedTargetListSerializer(DynamicModelSerializer):
    nickname = serializers.CharField(max_length=100, required=True)
    description = serializers.CharField(allow_blank=True, required=False)
    target = DynamicRelationField('EmbeddedTargetSerializer', required=False, many=True, embed=True)
    client = DynamicRelationField('EmbeddedClientSerializer', required=False, embed=True)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = TargetList
        fields = ('id', 'nickname', 'description', 'target', 'client',
                  'commit')
        read_only_fields = ('id',)

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        targets = validated_data.pop('target', list())

        if not commit:
            raise DRFValidationError({'commit': 'The commit flag may not be'
                                      ' set to false with POST requests for'
                                      ' the target-lists resource.'})
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
            if targets is not None:
                for each in targets:
                    instance.target.add(each)

        return instance

    def update(self, instance, validated_data):
        instance.nickname = validated_data.get('nickname', instance.nickname)
        instance.description = validated_data.get('description',
                                                  instance.description)
        instance.client = validated_data.get('client', instance.client)

        if validated_data.get('target', None) is not None:
            targets = validated_data.pop('target')
        else:
            targets = None

        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
            if targets is not None:
                instance.target.clear()
                for each in targets:
                    instance.target.add(each)

        return instance


class EmbeddedTargetListFlatSerializer(DynamicModelSerializer):
    nickname = serializers.CharField(max_length=100)
    description = serializers.CharField()
    client = DynamicRelationField('EmbeddedClientSerializer', embed=True)
    target = serializers.PrimaryKeyRelatedField(queryset=Target.objects.all(), many=True)

    class Meta:
        model = TargetList
        fields = ('id', 'nickname', 'description', 'client', 'target')
        read_only_fields = ('id',)

    def to_representation(self, target_list):
        all_targets = list()

        data = super(EmbeddedTargetListFlatSerializer, self).to_representation(target_list)

        for each_target in target_list.target.all():
            target = {
                'id': each_target.id,
                'email': each_target.email,
                'firstname': each_target.firstname,
                'lastname': each_target.lastname,
                # The target's actual timezone should be used because the
                # TargetList editor is not supposed to display the fallback
                # timezone in the spreadsheet view.
                'timezone': each_target.timezone
            }

            for datum in TargetDatum.objects.filter(target=each_target,
                                                    target_list=target_list):
                target[datum.label] = datum.value

            all_targets.append(target)

        data['target'] = all_targets

        return data


class EmbeddedVectorEmailSerializer(DynamicModelSerializer):
    # custom_state = serializers.BooleanField(default=False)
    state = serializers.IntegerField(required=False)
    engagement = DynamicRelationField('EmbeddedEngagementSerializer', required=True, embed=True)
    target = DynamicRelationField('EmbeddedTargetSerializer', required=True, embed=True)
    result_event = DynamicRelationField('EmbeddedResultEventSerializer', required=False, many=True, embed=True)
    # custom_email_template = serializers.BooleanField(default=False)
    # email_template = DynamicRelationField('EmbeddedEmailTemplateSerializer', required=True, embed=True)
    # custom_landing_page = serializers.BooleanField(default=False)
    # landing_page = DynamicRelationField('EmbeddedLandingPageSerializer', required=True, embed=True)
    # custom_redirect_page = serializers.BooleanField(default=False)
    # redirect_page = DynamicRelationField('EmbeddedRedirectPageSerializer', required=True, embed=True)
    # custom_send_at = serializers.BooleanField(default=False)
    send_at = serializers.DateTimeField(allow_null=True, required=False)
    sent_timestamp = serializers.DateTimeField(allow_null=True, required=False)
    error = serializers.CharField(allow_null=True, allow_blank=True, default='')

    class Meta:
        model = VectorEmail
        fields = ('id', 'state', 'engagement', 'target', 'result_event',
                  'send_at', 'sent_timestamp', 'error')
        # Everything for now. Custom fields are 1+ extra tickets.
        read_only_fields = ('id', 'state', 'engagement', 'target',
                            'result_event', 'send_at', 'sent_timestamp',
                            'error')


class EmbeddedEngagementSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=100, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    domain = DynamicRelationField('EmbeddedPhishingDomainSerializer', required=True, embed=True)
    path = serializers.CharField(max_length=100, default='')
    schedule = DynamicRelationField('EmbeddedScheduleSerializer', required=True, embed=True)
    email_server = DynamicRelationField('EmbeddedEmailServerSerializer', required=True, embed=True)
    email_template = DynamicRelationField('EmbeddedEmailTemplateSerializer', required=True, embed=True)
    landing_page = DynamicRelationField('EmbeddedLandingPageSerializer', required=True, embed=True)
    redirect_page = DynamicRelationField('EmbeddedRedirectPageSerializer', required=True, embed=True)
    target_lists = DynamicRelationField('EmbeddedTargetListSerializer', required=True, many=True, embed=True)
    campaign = DynamicRelationField('EmbeddedCampaignSerializer', required=True, embed=True)
    state = serializers.IntegerField(required=False)
    start_type = serializers.ChoiceField(choices=Engagement.START_TYPES, required=True, allow_blank=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    start_time = serializers.TimeField(required=False, allow_null=True)

    commit = serializers.BooleanField(default=False, write_only=True)
    process_error = DynamicMethodField()

    class Meta:
        model = Engagement
        fields = ('id', 'name', 'description', 'domain', 'path', 'schedule',
                  'email_server', 'email_template', 'landing_page',
                  'redirect_page', 'target_lists', 'campaign', 'state',
                  'start_type', 'start_date', 'start_time', 'commit',
                  'process_error')
        read_only_fields = ('id', 'process_error')

    def get_process_error(self, instance):
        code, text = instance.current_process_error
        if code is None and text is None:
            return {'error_code': '', 'error_text': ''}
        else:
            return {'error_code': code, 'error_text': text}

    def validate(self, data):
        if self.instance is None:
            start_type = data.get('start_type', 'immediate')
            start_date = data.get('start_date', None)
            start_time = data.get('start_time', None)
        else:
            start_type = data.get('start_type', self.instance.start_type)
            start_date = data.get('start_date', self.instance.start_date)
            start_time = data.get('start_time', self.instance.start_time)

        errors = dict()

        if start_type == 'immediate':
            if start_date is not None:
                errors['start_date'] = ['start_type "immediate" may not use a start_date']
            if start_time is not None:
                errors['start_time'] = ['start_type "immediate" may not use a start_time']
        elif start_type == 'countdown':
            if start_date is not None:
                errors['start_date'] = ['start_type "countdown" may not use a start_date']
            if start_time is None:
                errors['start_time'] = ['start_type "countdown" must have a start_time']
        elif start_type == 'specific_date':
            if start_date is None:
                errors['start_date'] = ['start_type "specific_date" must have a start_date']
            if start_time is None:
                errors['start_time'] = ['start_type "specific_date" must have a start_time']
            server_timezone = dj_tz.get_default_timezone()
            start_datetime = dj_tz.datetime(
                year=start_date.year,
                month=start_date.month,
                day=start_date.day,
                hour=start_time.hour,
                minute=start_time.minute,
                second=start_time.second
            )
            if server_timezone.localize(start_datetime) < dj_tz.now():
                errors['start_date'] = ['start_type "specific_date" engagements\' start_date and start_time fields must specify a time in the future']
                errors['start_time'] = ['start_type "specific_date" engagements\' start_date and start_time fields must specify a time in the future']

        if errors:
            raise DRFValidationError(errors)

        return data

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        target_lists = validated_data.pop('target_lists', list())

        if validated_data.get('state', None) is not None:
            validated_data.pop('state')

        if not commit:
            raise DRFValidationError({'commit': 'The commit flag may not be'
                                      ' set to false with POST requests for'
                                      ' the engagements resource.'})
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
            if target_lists is not None:
                for each in target_lists:
                    instance.target_lists.add(each)
                instance.create_vector_emails()

        return instance

    def update(self, instance, validated_data):
        if validated_data.get('state', None) is not None:
            validated_data.pop('state')

        commit = validated_data.get('commit', False)

        if instance.state == 1 and commit is True:
            error = APIException('Engagement {} is in progress and may not be'
                                 ' altered.'.format(instance.id))
            error.status_code = status.HTTP_409_CONFLICT
            raise error

        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description',
                                                  instance.description)
        instance.domain = validated_data.get('domain', instance.domain)
        instance.path = validated_data.get('path', instance.path)
        instance.schedule = validated_data.get('schedule', instance.schedule)
        instance.email_server = validated_data.get('email_server',
                                                   instance.email_server)
        instance.email_template = validated_data.get('email_template',
                                                     instance.email_template)
        instance.landing_page = validated_data.get('landing_page',
                                                   instance.landing_page)
        instance.redirect_page = validated_data.get('redirect_page',
                                                    instance.redirect_page)
        instance.campaign = validated_data.get('campaign', instance.campaign)
        instance.start_type = validated_data.get('start_type',
                                                 instance.start_type)
        instance.start_date = validated_data.get('start_date',
                                                 instance.start_date)
        instance.start_time = validated_data.get('start_time',
                                                 instance.start_time)
        target_lists = validated_data.pop('target_lists', None)

        if target_lists is not None and target_lists != instance.target_lists:
            raise DRFValidationError({'target_lists': 'Existing engagagements'
                                      ' may not change their target_lists.'})
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
            # New VectorEmails should only be created when their Engagement is
            # created.

        return instance


class EmbeddedOAuthEngagementSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=100, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    domain = DynamicRelationField('EmbeddedPhishingDomainSerializer', required=False, write_only=True, embed=True)
    path = serializers.CharField(max_length=100, required=False, write_only=True)
    schedule = DynamicRelationField('EmbeddedScheduleSerializer', required=True, embed=True)
    email_server = DynamicRelationField('EmbeddedEmailServerSerializer', required=True, embed=True)
    email_template = DynamicRelationField('EmbeddedEmailTemplateSerializer', required=True, embed=True)
    landing_page = DynamicRelationField('EmbeddedLandingPageSerializer', required=False, write_only=True, embed=True)
    redirect_page = DynamicRelationField('EmbeddedRedirectPageSerializer', required=False, write_only=True, embed=True)
    target_lists = DynamicRelationField('EmbeddedTargetListSerializer', required=True, many=True, embed=True)
    campaign = DynamicRelationField('EmbeddedCampaignSerializer', required=True, embed=True)
    state = serializers.IntegerField(required=False)
    oauth_consumer = DynamicRelationField('EmbeddedOAuthConsumerSerializer', required=True, embed=True)
    start_type = serializers.ChoiceField(choices=OAuthEngagement.START_TYPES, required=True, allow_blank=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    start_time = serializers.TimeField(required=False, allow_null=True)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = OAuthEngagement
        fields = ('id', 'name', 'description', 'domain', 'path', 'schedule',
                  'email_server', 'email_template', 'landing_page',
                  'redirect_page', 'target_lists', 'campaign', 'state',
                  'oauth_consumer', 'start_type', 'start_date', 'start_time',
                  'commit')
        read_only_fields = ('id', 'domain', 'path')

    def validate(self, data):
        if self.instance is None:
            start_type = data.get('start_type', 'immediate')
            start_date = data.get('start_date', None)
            start_time = data.get('start_time', None)
        else:
            start_type = data.get('start_type', self.instance.start_type)
            start_date = data.get('start_date', self.instance.start_date)
            start_time = data.get('start_time', self.instance.start_time)

        errors = dict()

        if start_type == 'immediate':
            if start_date is not None:
                errors['start_date'] = ['start_type "immediate" may not use a start_date']
            if start_time is not None:
                errors['start_time'] = ['start_type "immediate" may not use a start_time']
        elif start_type == 'countdown':
            if start_date is not None:
                errors['start_date'] = ['start_type "countdown" may not use a start_date']
            if start_time is None:
                errors['start_time'] = ['start_type "countdown" must have a start_time']
        elif start_type == 'specific_date':
            if start_date is None:
                errors['start_date'] = ['start_type "specific_date" must have a start_date']
            if start_time is None:
                errors['start_time'] = ['start_type "specific_date" must have a start_time']
            server_timezone = dj_tz.get_default_timezone()
            start_datetime = dj_tz.datetime(
                year=start_date.year,
                month=start_date.month,
                day=start_date.day,
                hour=start_time.hour,
                minute=start_time.minute,
                second=start_time.second
            )
            if server_timezone.localize(start_datetime) < dj_tz.now():
                errors['start_date'] = ['start_type "specific_date" engagements\' start_date and start_time fields must specify a time in the future']
                errors['start_time'] = ['start_type "specific_date" engagements\' start_date and start_time fields must specify a time in the future']

        if errors:
            raise DRFValidationError(errors)

        return data

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        target_lists = validated_data.pop('target_lists', list())

        if validated_data.get('state', None) is not None:
            validated_data.pop('state')

        if not commit:
            raise DRFValidationError({'commit': 'The commit flag may not be'
                                      ' set to false with POST requests for'
                                      ' the oauth-engagements resource.'})

        for field in ('domain', 'path', 'landing_page', 'redirect_page'):
            if validated_data.get(field, None) is not None:
                raise DRFValidationError({field: 'The {} field is not used by'
                                          ' OAuthEngagements.'.format(field)})
        try:
            # Can't use clean_fields due to the blank=False restriction
            # inherited from Engagement.
            instance = self.Meta.model(**validated_data)
            if commit:
                instance.save()
                if target_lists is not None:
                    for each in target_lists:
                        instance.target_lists.add(each)
                    instance.create_vector_emails()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        return instance

    def update(self, instance, validated_data):
        if validated_data.get('state', None) is not None:
            validated_data.pop('state')

        if instance.state == 1:
            error = APIException('OAuthEngagement {} is in progress and may'
                                 ' not be altered.'.format(instance.id))
            error.status_code = status.HTTP_409_CONFLICT
            raise error

        for field in ('domain', 'path', 'landing_page', 'redirect_page'):
            if validated_data.get(field, None) is not None:
                raise DRFValidationError({field: 'The {} field is not used by'
                                          ' OAuthEngagements.'.format(field)})

        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description',
                                                  instance.description)
        instance.domain = validated_data.get('domain', instance.domain)
        instance.path = validated_data.get('path', instance.path)
        instance.schedule = validated_data.get('schedule', instance.schedule)
        instance.email_server = validated_data.get('email_server',
                                                   instance.email_server)
        instance.email_template = validated_data.get('email_template',
                                                     instance.email_template)
        instance.landing_page = validated_data.get('landing_page',
                                                   instance.landing_page)
        instance.redirect_page = validated_data.get('redirect_page',
                                                    instance.redirect_page)
        instance.campaign = validated_data.get('campaign', instance.campaign)
        instance.oauth_consumer = validated_data.get('oauth_consumer',
                                                     instance.oauth_consumer)
        instance.start_type = validated_data.get('start_type',
                                                 instance.start_type)
        instance.start_date = validated_data.get('start_date',
                                                 instance.start_date)
        instance.start_time = validated_data.get('start_time',
                                                 instance.start_time)

        if validated_data.pop('target_lists', None) != instance.target_lists:
            raise DRFValidationError({'target_lists': 'Existing'
                                      ' oauth-engagagements may not change'
                                      ' their target_lists.'})
        try:
            # Can't use clean_fields due to the blank=False restriction on
            # fields OAuthEngagements don't use inherited from Engagement.
            # (One possible solution is to set them all to None on the model.)
            if validated_data.get('commit', False):
                instance.save()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        return instance


class EmbeddedOAuthConsumerSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=256, required=True)
    description = serializers.CharField(allow_blank=True, required=False)
    client_id = serializers.CharField(max_length=256, required=True)
    client_secret = serializers.CharField(max_length=256, required=True)
    scope = serializers.CharField(max_length=256, required=True)
    callback_url = serializers.CharField(max_length=256, required=True)
    bounce_url = serializers.CharField(max_length=256, required=True)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = OAuthConsumer
        fields = ('id', 'name', 'description', 'client_id', 'client_secret',
                  'scope', 'callback_url', 'bounce_url', 'commit')
        read_only_fields = ('id',)

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description',
                                                  instance.description)
        instance.client_id = validated_data.get('client_id',
                                                instance.client_id)
        instance.client_secret = validated_data.get('client_secret',
                                                    instance.client_secret)
        instance.scope = validated_data.get('scope', instance.scope)
        instance.callback_url = validated_data.get('callback_url',
                                                   instance.callback_url)
        instance.bounce_url = validated_data.get('bounce_url',
                                                 instance.bounce_url)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedOAuthResultSerializer(DynamicModelSerializer):
    timestamp = serializers.DateTimeField(required=True)
    userAgent = serializers.CharField(max_length=255, required=True)
    ip = serializers.IPAddressField(required=True)
    email = serializers.CharField(max_length=255, required=True)
    oauth_engagement = DynamicRelationField('EmbeddedOAuthEngagementSerializer', embed=True,
                                            required=False)
    target = DynamicRelationField('EmbeddedTargetSerializer', embed=True,
                                  required=False)
    consumer = DynamicRelationField('EmbeddedOAuthConsumerSerializer', embed=True,
                                    required=False)

    class Meta:
        model = OAuthResult
        fields = ('id', 'timestamp', 'userAgent', 'ip', 'email',
                  'oauth_engagement', 'target', 'consumer')
        # Only OAuth grants should be making OAuthResults.
        read_only_fields = ('id', 'timestamp', 'userAgent', 'ip', 'email',
                            'oauth_engagement', 'target', 'consumer')


class EmbeddedPlunderSerializer(DynamicModelSerializer):
    oauth_result = DynamicRelationField('EmbeddedOAuthResultSerializer', embed=True,
                                        required=False)
    path = serializers.CharField(max_length=255, required=False)
    file_id = serializers.CharField(max_length=255, required=False)
    filename = serializers.CharField(max_length=255, required=False)
    mimetype = serializers.CharField(max_length=255, required=False)
    last_modified = serializers.DateTimeField(required=False)
    data = serializers.CharField(required=False)

    class Meta:
        model = Plunder
        fields = ('id', 'oauth_result', 'path', 'file_id', 'filename',
                  'mimetype', 'last_modified', 'data')
        read_only_fields = ('id', 'oauth_result', 'path', 'file_id',
                            'filename', 'mimetype', 'last_modified', 'data')


class EmbeddedShoalScrapeCredsSerializer(DynamicModelSerializer):
    name = serializers.CharField(max_length=255, required=True)
    username = serializers.CharField(max_length=255, required=True)
    password = serializers.CharField(max_length=255, required=True)
    scraper_user_agent = DynamicRelationField('EmbeddedScraperUserAgentSerializer', embed=True,
                                              required=False)
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = ShoalScrapeCreds
        fields = ('id', 'name', 'username', 'password', 'scraper_user_agent',
                  'commit')
        read_only_fields = ('id',)

    def create(self, validated_data):
        commit = validated_data.pop('commit')
        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.username = validated_data.get('username', instance.username)
        instance.password = validated_data.get('password', instance.password)
        instance.scraper_user_agent = validated_data.get('scraper_user_agent',
                                                   instance.scraper_user_agent)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if validated_data.get('commit', False):
            instance.save()
        return instance


class EmbeddedShoalScrapeTaskSerializer(DynamicModelSerializer):
    state = serializers.IntegerField(required=False)
    shoalscrape_creds = DynamicRelationField('EmbeddedShoalScrapeCredsSerializer', embed=True,
                                             required=True)
    company = serializers.CharField(max_length=255, required=True)
    domain = serializers.CharField(max_length=255, required=True)
    company_linkedin_id = serializers.CharField(max_length=255, required=True)
    path = serializers.CharField(max_length=255, required=False)
    last_started_at = serializers.DateTimeField(required=False)
    error = serializers.CharField(default='')
    current_task_id = serializers.CharField(max_length=36, default='',
                                            help_text='The task ID of the'
                                            ' Celery worker currently running'
                                            ' this task, or an empty string')
    commit = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = ShoalScrapeTask
        fields = ('id', 'state', 'shoalscrape_creds', 'company', 'domain',
                  'company_linkedin_id', 'path', 'last_started_at', 'error',
                  'current_task_id', 'commit')
        read_only_fields = ('id', 'state', 'path', 'last_started_at', 'error',
                            'current_task_id')

    def create(self, validated_data):
        commit = validated_data.pop('commit')

        if validated_data.get('state', None) is not None:
            validated_data.pop('state')

        try:
            instance = self.Meta.model(**validated_data)
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
            instance.set_log_file_path()
            instance.initialize_task()
        return instance

    def update(self, instance, validated_data):
        if validated_data.get('state', None) is not None:
            validated_data.pop('state')

        commit = validated_data.get('commit', False)

        if instance.state == 1 and commit is True:
            error = APIException('ShoalScrapeTask {} is in progress and may'
                                 ' not be altered.'.format(instance.id))
            error.status_code = status.HTTP_409_CONFLICT
            raise error

        instance.shoalscrape_creds = validated_data.get('shoalscrape_creds',
                                                    instance.shoalscrape_creds)
        instance.company = validated_data.get('company', instance.company)
        instance.domain = validated_data.get('domain', instance.domain)
        instance.company_linkedin_id = validated_data.get('company_linkedin_id',
                                                  instance.company_linkedin_id)
        instance.path = validated_data.get('path', instance.path)
        instance.last_started_at = validated_data.get('last_started_at',
                                                      instance.last_started_at)
        instance.error = validated_data.get('error', instance.error)
        instance.current_task_id = validated_data.get('current_task_id',
                                                      instance.current_task_id)
        try:
            instance.clean_fields()
        except DjangoValidationError as e:
            raise convert_validation_error(e)

        if commit:
            instance.save()
            instance.set_log_file_path()
            instance.initialize_task()
        return instance


class EmbeddedEmailLogSerializer(DynamicEphemeralSerializer):
    target = DynamicRelationField('EmbeddedTargetSerializer', embed=True)
    engagement = DynamicRelationField('EmbeddedEngagementSerializer', embed=True)
    id = serializers.IntegerField()
    state = serializers.IntegerField()
    send_at = serializers.DateTimeField()
    sent_timestamp = serializers.DateTimeField()
    error = serializers.CharField()

    target_list_nickname = serializers.CharField()
    target_list_id = serializers.IntegerField()
    targeted_oauth_result_id = serializers.IntegerField()
    client_name = serializers.CharField()
    client_id = serializers.IntegerField()
    campaign_name = serializers.CharField()
    campaign_id = serializers.IntegerField()
    target_timezone = serializers.CharField()

    class Meta:
        model = VectorEmail
        name = 'email_log'

    def get_model(self, *args, **kwargs):
        return VectorEmail

    def to_representation(self, instance):
        data = dict()
        data['id'] = data['pk'] = instance.id
        data['state'] = instance.state
        data['send_at'] = instance.send_at
        data['sent_timestamp'] = instance.sent_timestamp
        data['error'] = instance.error

        try:
            data['target'] = instance.target
            # Not the same as Target.timezone; this displays the actual sending
            # timezone used by the email, so it needs to include the Target's
            # Client's timezone.
            data['target_timezone'] = instance.target.get_timezone()
        except:
            data['target'] = None
            data['target_timezone'] = None

        try:
            data['engagement'] = instance.engagement
        except:
            data['engagement'] = None

        try:
            target_list = TargetList.objects.get(target=instance.target,
                                                 engagement=instance.engagement)
            data['target_list_id'] = target_list.id
            data['target_list_nickname'] = target_list.nickname
        except:
            data['target_list_id'] = None
            data['target_list_nickname'] = None

        # In the email log, the only OAuthResults that need to be displayed are
        # the ones coming from the target - whose email is already in the data.
        try:
            data['targeted_oauth_result_id'] = instance.targeted_oauth_result.id
        except:
            data['targeted_oauth_result_id'] = None

        try:
            client = instance.engagement.campaign.client
            data['client_id'] = client.id
            data['client_name'] = client.name
        except:
            data['client_id'] = None
            data['client_name'] = None

        try:
            campaign = instance.engagement.campaign
            data['campaign_id'] = campaign.id
            data['campaign_name'] = campaign.name
        except:
            data['campaign_id'] = None
            data['campaign_name'] = None

        email_log_entry = EphemeralObject(data)

        return super(EmbeddedEmailLogSerializer, self).to_representation(
            email_log_entry
        )


class EmbeddedOAuthConsoleSerializer(DynamicEphemeralSerializer):
    id = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    userAgent = serializers.CharField()
    ip = serializers.IPAddressField()
    email = serializers.CharField()
    oauth_engagement = DynamicRelationField('EmbeddedOAuthEngagementSerializer', embed=True)
    target = DynamicRelationField('EmbeddedTargetSerializer', embed=True)
    consumer = DynamicRelationField('EmbeddedOAuthConsumerSerializer', embed=True)

    available_scopes = serializers.ListField()
    plunder = DynamicRelationField('EmbeddedPlunderSerializer', embed=True, many=True)

    class Meta:
        model = OAuthResult
        name = 'oauth_console'

    def get_model(self, *args, **kwargs):
        return OAuthResult

    def to_representation(self, instance):
        data = dict()
        data['id'] = data['pk'] = instance.id
        data['timestamp'] = instance.timestamp
        data['userAgent'] = instance.userAgent
        data['ip'] = instance.ip
        data['email'] = instance.email
        data['oauth_engagement'] = instance.oauth_engagement
        data['target'] = instance.target
        data['consumer'] = instance.consumer

        try:
            available_scopes = list()
            # This is the list of known scopes.
            for each in ('gmail', 'drive'):
                if instance.consumer.scope.find(each) > 0:
                    available_scopes.append(each)
            data['available_scopes'] = available_scopes
        except:
            data['available_scopes'] = list()

        try:
            data['plunder'] = Plunder.objects.filter(oauth_result__email=instance.email)
        except:
            data['plunder'] = list()

        oauth_console = EphemeralObject(data)

        return super(EmbeddedOAuthConsoleSerializer, self).to_representation(
            oauth_console
        )


class EmbeddedPhishingResultSerializer(DynamicEphemeralSerializer):
    id = serializers.IntegerField()
    event_type = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    userAgent = serializers.CharField()
    ip = serializers.IPAddressField()
    login = serializers.CharField()
    password = serializers.CharField()
    raw_data = serializers.CharField()
    vector_email = DynamicRelationField('EmbeddedVectorEmailSerializer',
                                        deferred=True, many=True, embed=True)

    target_lists = DynamicComputedField()

    class Meta:
        model = ResultEvent
        name = 'phishing_result'

    def get_model(self, *args, **kwargs):
        return ResultEvent

    def to_representation(self, instance):
        data = dict()
        data['id'] = data['pk'] = instance.id
        data['timestamp'] = instance.timestamp
        data['event_type'] = instance.event_type
        data['userAgent'] = instance.userAgent
        data['ip'] = instance.ip
        data['login'] = instance.login
        data['password'] = instance.password
        data['raw_data'] = instance.raw_data

        try:
            vector_emails = VectorEmail.objects.filter(result_event=instance)
            data['vector_email'] = vector_emails
        except:
            data['vector_email'] = list()

        # Include only the TargetLists this ResultEvent's Target is a part of.
        try:
            vector_email = vector_emails.get()
            target = vector_email.target
            engagement = vector_email.engagement
            target_lists = engagement.target_lists.filter(target=target)
        except ObjectDoesNotExist:
            target_lists = TargetList.objects.none()

        # Embedding for a non-model-field relation.
        serialized_target_lists = list()
        for each_target_list in target_lists:
            serialized = EmbeddedTargetListSerializer(each_target_list)
            serialized_target_lists.append(serialized.data)
        data['target_lists'] = serialized_target_lists

        phishing_result = EphemeralObject(data)

        return super(EmbeddedPhishingResultSerializer, self).to_representation(
            phishing_result
        )
