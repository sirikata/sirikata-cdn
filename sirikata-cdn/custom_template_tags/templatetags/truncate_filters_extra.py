from django import template
register = template.Library()

@register.filter
def truncate_chars(value, max_length):
    if value is None:
        return ""
    if len(value) <= max_length:
        return value

    truncd_val = value[:max_length-3]
    
    return truncd_val + "..."
