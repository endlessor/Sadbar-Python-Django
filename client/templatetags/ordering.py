# -*- coding: utf-8 -*-
from django import template

register = template.Library()


@register.simple_tag
def order_filter(sortings, request, order_by):
    sorting_list = []
    if sortings:
        sorting_list = sortings.split(',')
        if '-%s' % order_by in sorting_list:
            index = sorting_list.index('-%s' % order_by)
            sorting_list.pop(index)
        elif order_by.lstrip('-') in sorting_list:
            index = sorting_list.index(order_by.lstrip('-'))
            sorting_list[index] = order_by
        elif '-%s' % order_by in sorting_list:
            index = sorting_list.index('-%s' % order_by)
            sorting_list[index] = order_by
        else:
            sorting_list.append(order_by)
    else:
        sorting_list.append(order_by)

    response = '?order_by=%s' % ','.join(sorting_list)
    if request and int(request.GET.get('client', 0)) > 0:
        response += '&client=%s' % request.GET['client']
    if request and request.GET.get('filter_target'):
        response += '&filter_target=%s' % request.GET['filter_target']
    if request and request.GET.get('filter_status'):
        response += '&filter_status=%s' % request.GET['filter_status']
    if request and int(request.GET.get('page', 0)) > 1:
        response += '&page=%s' % request.GET['page']

    return response
