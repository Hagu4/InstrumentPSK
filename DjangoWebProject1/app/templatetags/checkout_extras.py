from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='get_item_index')
def get_item_index(sequence, item):
    """
    Returns the 0-based index of an item in a list.
    Returns -1 if the item is not in the list.
    """
    try:
        return sequence.index(item)
    except ValueError:
        return -1

@register.filter(name='get_prev_step')
def get_prev_step(sequence, current_item):
    """
    Returns the previous item in a list.
    Returns the first item if the current item is not found or is the first.
    """
    try:
        current_index = sequence.index(current_item)
        if current_index > 0:
            return sequence[current_index - 1]
    except ValueError:
        pass
    # Default to the first step in case of an error or if it's the first step
    return sequence[0] if sequence else ''
