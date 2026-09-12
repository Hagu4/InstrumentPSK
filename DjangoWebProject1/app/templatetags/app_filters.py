from django import template

register = template.Library()

@register.filter
def get_range(value):
    """
    Filter to create a range suitable for iterating in templates.
    Usage: {% for i in 5|get_range %}
    """
    return range(value)

@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def divisibleby(value, arg):
    """
    Filter to divide a value by an argument
    Usage: {{ value|divisibleby:10 }}
    """
    try:
        return int(int(value) / int(arg))
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def format_price(value):
    """
    Formats a number with thousands separators (spaces).
    Usage: {{ 42200|format_price }} -> 42 200
    """
    if value is None:
        return ""
    try:
        # Use comma as separator then replace with space for Russian locale style
        return "{:,.0f}".format(float(value)).replace(",", " ")
    except (ValueError, TypeError):
        return value
