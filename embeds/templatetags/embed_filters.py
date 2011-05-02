import re
from datetime import datetime
from hashlib import md5
from django import template
from django.core.cache import cache
from django.conf import settings
from embedly import Embedly
from embeds.models import SavedEmbed

register = template.Library()

EMBED_REGEX = re.compile(r'embed:\s*(http[^\s]+)', re.I)
USER_AGENT = 'Mozilla/5.0 (compatible; TheBayCitizen/0.1; ' \
        '+http://www.baycitizen.org/)'

@register.filter
def embedly(html, arg=None):
    return EMBED_REGEX.sub(lambda x: embed_replace(x, maxwidth=arg), html)


def embed_replace(match, maxwidth=None):
    url = match.group(1)

    key = make_cache_key(url, maxwidth)
    cached_html = cache.get(key)

    if cached_html:
        return cached_html

    # call embedly API
    client = Embedly(user_agent=USER_AGENT)
    if maxwidth:
        oembed = client.oembed(url, maxwidth=maxwidth)
    else:
        oembed = client.oembed(url)

    # check database
    if oembed.error:
        try:
            html = SavedEmbed.objects.get(url=url, maxwidth=maxwidth).html
            cache.set(key, html)
            return html
        except SavedEmbed.DoesNotExist:
            return 'Error embedding %s' % url

    # save result to database
    row, created = SavedEmbed.objects.get_or_create(url=url, maxwidth=maxwidth,
                defaults={'type': oembed.type})

    if oembed.type == 'photo':
        html = '<img src="%s" width="%s" height="%s" />' % (oembed.url,
                oembed.width, oembed.height)
    else:
        html = oembed.html

    row.html = html
    row.last_updated = datetime.now()
    row.save()

    # set cache
    cache.set(key, html, 86400)
    return html


def make_cache_key(url, maxwidth=None):
    md5_hash = md5(url).hexdigest()
    return "embeds.%s.%s" % (maxwidth if maxwidth else 'default', md5_hash)
