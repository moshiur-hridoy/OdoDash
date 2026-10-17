def test_linkify_filter(app):
    f = app.jinja_env.filters['linkify']
    out = str(f('See https://paperless.example/doc/1, thanks'))
    assert '<a href="https://paperless.example/doc/1"' in out
    assert 'rel="noopener noreferrer nofollow"' in out
    assert out.endswith('</a>, thanks')


def test_linkify_escapes_html_and_ignores_unsafe_schemes(app):
    f = app.jinja_env.filters['linkify']
    out = str(f('<script>alert(1)</script> javascript:alert(1) ftp://x'))
    assert '<script>' not in out
    assert '<a ' not in out


def test_linkify_handles_empty(app):
    f = app.jinja_env.filters['linkify']
    assert f(None) == ''
