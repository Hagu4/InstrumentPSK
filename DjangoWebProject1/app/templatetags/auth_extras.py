from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    group = Group.objects.get(name=group_name)
    return group in user.groups.all()

@register.simple_tag(takes_context=True)
def is_manager(context):
    user = context['user']
    return user.groups.filter(name='Менеджер').exists()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
