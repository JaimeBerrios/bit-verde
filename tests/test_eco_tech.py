from io import BytesIO
from unittest.mock import patch

import pytest

from app.services import eco_tech

HTML = '''<div class="hero-content"><h1>Nuestro impacto</h1>
<div class="modules"><div class="module-card"><h3>12</h3><p>Dispositivos recibidos</p></div>
<div class="module-card"><h3>8</h3><p>Participantes registrados</p></div></div>
<h2>Residuos por categoría</h2>{categories}</div>'''


def test_statistics_preserve_remote_counts_and_categories():
    data = eco_tech.parse_statistics(HTML.format(categories='<table><tr><td>Teléfonos</td><td>7</td></tr><tr><td>Cables</td><td>5</td></tr></table>'))
    assert data['metrics'] == [{'value': '12', 'label': 'Dispositivos recibidos'},
                               {'value': '8', 'label': 'Participantes registrados'}]
    assert data['categories'] == ['Teléfonos 7', 'Cables 5']
    empty = eco_tech.parse_statistics(HTML.format(categories='<p>Todavía no hay residuos registrados.</p>'))
    assert empty['categories'] == ['Todavía no hay residuos registrados.']
    with pytest.raises(ValueError):
        eco_tech.parse_statistics('<html>Página de error</html>')


def test_statistics_cache_and_failure_keep_last_real_data(monkeypatch):
    monkeypatch.setattr(eco_tech, '_cached', None)
    monkeypatch.setattr(eco_tech, '_next_refresh', 0)
    monkeypatch.setattr(eco_tech, '_failed', False)
    raw = HTML.format(categories='<p>Sin residuos.</p>').encode()
    with patch.object(eco_tech, 'urlopen', return_value=BytesIO(raw)) as fetch:
        first = eco_tech.statistics()
        assert not first['stale']
        assert eco_tech.statistics() == first
        assert fetch.call_count == 1
    monkeypatch.setattr(eco_tech, '_next_refresh', 0)
    with patch.object(eco_tech, 'urlopen', side_effect=OSError('offline')):
        stale = eco_tech.statistics()
    assert stale['stale']
    assert stale['metrics'] == first['metrics']
    assert stale['updated_at'] == first['updated_at']


def test_first_connection_failure_does_not_invent_zero_counts(monkeypatch):
    monkeypatch.setattr(eco_tech, '_cached', None)
    monkeypatch.setattr(eco_tech, '_next_refresh', 0)
    monkeypatch.setattr(eco_tech, '_failed', False)
    with patch.object(eco_tech, 'urlopen', side_effect=OSError('offline')):
        with pytest.raises(ValueError, match='No se pudo consultar'):
            eco_tech.statistics()
