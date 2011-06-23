from django import template

from django.template import Library, Node, resolve_variable, TemplateSyntaxError
from django.template import Context, Template, Node, resolve_variable, TemplateSyntaxError, Variable

register = template.Library()


"""
This is custom tag I wrote for myself for solving situations when you have filter form and page
numbers in the same page. You want to change ?page=.. or add it if it doesn't exist to save
filter form data while moving through pages.

Usage: place this code in your application_dir/templatetags/add_get_parameter.py
In template: 
{% load add_get_parameter %}
<a href="{% add_get_paramater param1='const_value',param2=variable_in_context %}">
    Link with modified params
</a>

It's required that you have 'django.core.context_processors.request' in TEMPLATE_CONTEXT_PROCESSORS

URL: http://django.mar.lt/2010/07/add-get-parameter-tag.html
"""


class AddGetParameter(Node):
    def __init__(self, values):
        self.values = values
        
    def render(self, context):
        req = resolve_variable('request',context)
        params = req.GET.copy()
        for key, value in self.values.items():
            params[key] = Variable(value).resolve(context)
        return '?%s' %  params.urlencode()


@register.tag
def add_get_parameter(parser, token):
    from re import split
    contents = split(r'\s+', token.contents, 2)[1]
    pairs = split(r',', contents)
    
    values = {}
    
    for pair in pairs:
        s = split(r'=', pair, 2)
        values[s[0]] = s[1]    
    
    return AddGetParameter(values)