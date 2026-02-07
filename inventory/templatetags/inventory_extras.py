import html
import json

from django import template
from django.utils.safestring import mark_safe

try:
    import markdown as markdown_lib
except ImportError:  # pragma: no cover
    markdown_lib = None

register = template.Library()


@register.filter(name="render_markdown")
def render_markdown(value):
    text = (value or "").strip()
    if not text:
        return ""
    safe_source = html.escape(text)
    if markdown_lib is None:
        return mark_safe(safe_source.replace("\n", "<br>"))
    rendered = markdown_lib.markdown(
        safe_source,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    return mark_safe(rendered)


@register.filter(name="pretty_json")
def pretty_json(value):
    try:
        return json.dumps(value or {}, indent=2, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return "{}"
