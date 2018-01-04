# -*- coding: utf-8 -*-
from django import template

register = template.Library()


@register.simple_tag
def make_pathsafe(text):
    return text.lower().replace(' ', '_')
