from urllib.parse import urlencode

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """
    Build a querystring while overriding some params.
    Example: {% qs page=2 %}
    """
    request = context["request"]
    params = request.GET.copy()
    for k, v in kwargs.items():
        if v is None or v == "":
            params.pop(k, None)
        else:
            params[k] = str(v)
    return "?" + urlencode(params, doseq=True) if params else ""

