from django.conf import settings


def current_branch(request):
    return {'current_branch': settings.CURRENT_BRANCH}


def current_version(request):
    return {'current_version': settings.SANDBAR_VERSION}


def accessed_path(request):
    return {'accessed_path': request.META.get('PATH_INFO')}
