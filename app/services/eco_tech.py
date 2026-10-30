"""Read public Eco-Tech statistics without executing or embedding remote HTML."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from threading import Lock
from time import monotonic
from urllib.request import Request, urlopen

from app.core.partners import ECO_TECH_STATS_URL


class Element:
    def __init__(self, tag='', attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def find(self, tag=None, class_name=None):
        for child in self.children:
            if isinstance(child, Element):
                if ((tag is None or child.tag == tag) and
                        (class_name is None or class_name in child.attrs.get('class', '').split())):
                    yield child
                yield from child.find(tag, class_name)

    def text(self):
        return ' '.join(' '.join(c.text() if isinstance(c, Element) else c
                                for c in self.children).split())


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        el = Element(tag, attrs)
        self.stack[-1].children.append(el)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                       'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(el)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if not any(el.tag in {'script', 'style'} for el in self.stack):
            self.stack[-1].children.append(data)


def parse_statistics(html):
    doc = Document()
    doc.feed(html)
    content = next(doc.root.find(class_name='hero-content'), None)
    if content is None:
        raise ValueError('Eco-Tech cambió la estructura de sus estadísticas.')
    metrics = []
    for card in content.find(class_name='module-card'):
        value = next(card.find('h3'), Element()).text()
        label = next(card.find('p'), Element()).text()
        if not re.fullmatch(r'[\d.,\s]+', value) or not label:
            raise ValueError('Eco-Tech devolvió una métrica no reconocida.')
        metrics.append({'value': value, 'label': label})
    if len(metrics) != 2:
        raise ValueError('Eco-Tech cambió sus métricas públicas.')
    categories = []
    heading_found = False
    for child in content.children:
        if not isinstance(child, Element):
            continue
        if child.tag == 'h2':
            heading_found = True
            continue
        if heading_found:
            rows = list(child.find('tr')) or list(child.find('li')) or list(child.find('p'))
            categories.extend(row.text() for row in rows or [child] if row.text())
    if not heading_found or not categories:
        raise ValueError('Eco-Tech no devolvió la sección de categorías.')
    return {'metrics': metrics, 'categories': categories}


_lock = Lock()
_cached = None
_next_refresh = 0
_failed = False


def statistics():
    global _cached, _next_refresh, _failed
    with _lock:
        if monotonic() >= _next_refresh:
            try:
                request = Request(ECO_TECH_STATS_URL, headers={'User-Agent': 'BitVerde/1.0'})
                with urlopen(request, timeout=5) as response:
                    raw = response.read(262145)
                    if len(raw) > 262144:
                        raise ValueError('La respuesta de Eco-Tech es demasiado grande.')
                    data = parse_statistics(raw.decode('utf-8'))
                _cached = {**data, 'updated_at': datetime.now(timezone.utc).isoformat()}
                _failed = False
            except (OSError, ValueError):
                _failed = True
            _next_refresh = monotonic() + 30
        if _cached is None:
            raise ValueError('No se pudo consultar Eco-Tech. Reintentando…')
        return {**_cached, 'stale': _failed}
