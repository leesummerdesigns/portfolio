#!/usr/bin/env python3
"""Build the German pages from the English ones.

    python3 i18n/build_de.py extract   # list English strings that have no German yet
    python3 i18n/build_de.py build     # write the German pages, patch the English ones

Needs beautifulsoup4 (pip install beautifulsoup4). Run from anywhere; paths are
relative to the repository root (the folder above this script).

i18n/config.json   page map: English path -> German path. Pages listed under
                   "existing" are hand-written German pages: the script only
                   gives them the shared German menu and the language switcher.
i18n/de/*.json     translations, {id: German}. Inline tags appear as <t0>..</t0>
                   placeholders; "=" means "same as English".
"""
import copy
import hashlib
import html
import json
import posixpath
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup as _Soup, Comment, NavigableString, Tag
from bs4.builder import HTMLParserTreeBuilder
from bs4.formatter import HTMLFormatter

class KeepOrder(HTMLFormatter):
    """Keep attribute order and write <br> instead of <br/>, like the English files."""
    def attributes(self, tag):
        return list(tag.attrs.items())


FMT = KeepOrder(entity_substitution=HTMLFormatter.REGISTRY['minimal'].entity_substitution,
                void_element_close_prefix=None, empty_attributes_are_booleans=True)


def BeautifulSoup(markup, _parser=None):
    # bs4 collapses whitespace-only text unless it sits in a "preserve" tag;
    # marking <html> keeps the original indentation.
    b = HTMLParserTreeBuilder()
    b.preserve_whitespace_tags = set(b.preserve_whitespace_tags) | {'html'}
    return _Soup(markup, builder=b)


ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / 'i18n/config.json').read_text())
DOMAIN = CFG['domain'].rstrip('/')

INLINE = {'a', 'abbr', 'b', 'br', 'cite', 'code', 'em', 'i', 'mark', 'q', 's',
          'small', 'span', 'strong', 'sub', 'sup', 'u', 'time', 'wbr'}
VOID = {'br', 'wbr'}
SKIP = {'script', 'style', 'svg', 'noscript', 'template', 'pre', 'iframe'}
ATTRS = ['alt', 'title', 'placeholder', 'aria-label']
META = {'description', 'keywords', 'og:title', 'og:description', 'og:image:alt',
        'twitter:title', 'twitter:description', 'twitter:image:alt'}
LD_KEYS = {'name', 'description', 'text', 'headline', 'jobTitle', 'alternativeHeadline',
           'abstract', 'skills', 'serviceType', 'knowsAbout', 'keywords', 'articleSection',
           'award', 'caption', 'educationalCredentialAwarded', 'disambiguatingDescription'}
LD_URL_KEYS = {'url', '@id', 'mainEntityOfPage', 'item'}
LETTER = re.compile(r'[A-Za-zÀ-ÿ]')
PH = re.compile(r'<(/?)t(\d+)(/?)>')

GLOBE = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" '
         'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
         '<circle cx="12" cy="12" r="9.25"/><path d="M2.75 12h18.5"/>'
         '<path d="M12 2.75c2.4 2.55 3.6 5.63 3.6 9.25s-1.2 6.7-3.6 9.25c-2.4-2.55-3.6-5.63-3.6-9.25'
         's1.2-6.7 3.6-9.25z"/></svg>')


def norm_path(p):
    p = p or '/'
    if p.endswith('/'):
        p += 'index.html'
    return p


PAGES = {norm_path(k): v for k, v in CFG['pages'].items()}       # en -> de
EXISTING = {norm_path(p) for p in CFG.get('existing', [])}
DE_TO_EN = {norm_path(v): k for k, v in PAGES.items()}


def file_of(site_path):
    return ROOT / norm_path(site_path).lstrip('/')


def pretty(site_path):
    """/de/index.html -> /de/ for links and canonicals."""
    return site_path[:-len('index.html')] if site_path.endswith('/index.html') else site_path


def sid(text):
    return hashlib.sha1(text.encode()).hexdigest()[:10]


def squash(s):
    return re.sub(r'\s+', ' ', s).strip()


# ---------------------------------------------------------------- segments

def inline_only(tag):
    return all(d.name in INLINE for d in tag.descendants if isinstance(d, Tag))


def has_letters(node):
    return bool(LETTER.search(node.get_text()))


def segment_root(tag):
    """Step into a lone inline wrapper (li > a > text) so the string stays plain."""
    while True:
        kids = [c for c in tag.children if not (isinstance(c, NavigableString) and not c.strip())]
        if len(kids) == 1 and isinstance(kids[0], Tag) and kids[0].name in INLINE - VOID:
            tag = kids[0]
        else:
            return tag


def serialize(tag):
    tags = []

    def ser(node):
        out = []
        for c in node.children:
            if isinstance(c, Comment):
                continue
            if isinstance(c, NavigableString):
                out.append(html.escape(str(c), quote=False))
            elif isinstance(c, Tag):
                i = len(tags)
                tags.append(c)
                out.append(f'<t{i}/>' if c.name in VOID else f'<t{i}>{ser(c)}</t{i}>')
        return ''.join(out)

    return squash(ser(tag)), tags


def skipped(node):
    for p in ([node] if isinstance(node, Tag) else []) + list(node.parents):
        classes = (p.get('class') or []) if isinstance(p, Tag) else []
        if isinstance(p, Tag) and (p.get('translate') == 'no' or 'notranslate' in classes
                                   or any(c.startswith('material-') for c in classes)):
            return True
    return False


def walk(el, found):
    for c in list(el.children):
        if isinstance(c, Comment):
            continue
        if isinstance(c, NavigableString):
            if LETTER.search(c) and not skipped(c.parent):
                found.append(('text', c))
        elif isinstance(c, Tag):
            if c.name in SKIP or skipped(c):
                continue
            if inline_only(c) and has_letters(c):
                found.append(('html', segment_root(c)))
            else:
                walk(c, found)


def ld_strings(obj, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from ld_strings(v, k)
    elif isinstance(obj, list):
        for v in obj:
            yield from ld_strings(v, key)
    elif isinstance(obj, str) and key in LD_KEYS and LETTER.search(obj) and not re.match(r'(https?:|mailto:)', obj):
        yield obj


def collect(soup):
    """Every translatable string on a page, in reading order: (id, english)."""
    out = []
    if soup.title and soup.title.string:
        out.append(squash(soup.title.string))
    for m in soup.find_all('meta'):
        if (m.get('name') or m.get('property')) in META and m.get('content'):
            out.append(squash(m['content']))
    for s in soup.find_all('script', type='application/ld+json'):
        out += [squash(x) for x in ld_strings(json.loads(s.string))]
    found = []
    walk(soup.body, found)
    for kind, node in found:
        out.append(squash(str(node)) if kind == 'text' else serialize(node)[0])
    for t in soup.body.find_all(True):
        if t.name in SKIP or skipped(t):
            continue
        for a in ATTRS:
            if t.get(a) and LETTER.search(t[a]):
                out.append(squash(t[a]))
        if t.name == 'input' and t.get('name') == 'subject' and t.get('value'):
            out.append(squash(t['value']))
    seen, res = set(), []
    for s in out:
        if s and s not in seen:
            seen.add(s)
            res.append((sid(s), s))
    return res


def parse_en(en_path):
    soup = BeautifulSoup(file_of(en_path).read_text(), 'html.parser')
    for d in soup.find_all('details', class_='lang-switch'):
        d.decompose()
    return soup


def load_dict():
    d = {}
    for f in sorted((ROOT / 'i18n/de').glob('*.json')):
        d.update(json.loads(f.read_text()))
    return d


# ---------------------------------------------------------------- translate

def tr(en, D, problems):
    en = squash(en)
    de = D.get(sid(en))
    if de is None:
        problems.append(f'missing {sid(en)}: {en[:80]}')
        return en
    return en if de == '=' else de


def map_url(url, src_page):
    """English link -> link for the German page (root-relative)."""
    if not url or url.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:')):
        return url
    parts = urlsplit(url)
    if parts.scheme in ('http', 'https'):
        if f'{parts.scheme}://{parts.netloc}' != DOMAIN:
            return url
        target = norm_path(parts.path)
        if target in PAGES:
            return DOMAIN + pretty(PAGES[target]) + (('?' + parts.query) if parts.query else '') + (('#' + parts.fragment) if parts.fragment else '')
        return url
    if parts.scheme:
        return url
    base = posixpath.dirname(norm_path(src_page))
    path = parts.path if parts.path.startswith('/') else posixpath.normpath(posixpath.join(base, parts.path))
    if parts.path.endswith('/') and not path.endswith('/'):
        path += '/'
    target = norm_path(path)
    if target in PAGES:
        path = pretty(PAGES[target])
    elif path.endswith('/index.html') and parts.path.endswith('/'):
        path = path[:-len('index.html')]
    return urlunsplit(('', '', path, parts.query, parts.fragment))


def map_srcset(v, src):
    return ', '.join(' '.join([map_url(p.split()[0], src)] + p.split()[1:]) for p in v.split(',') if p.strip())


def switcher(en_path, de_path, lang):
    en_href, de_href = pretty(en_path), pretty(de_path)
    if en_href == '/index.html':
        en_href = '/'
    label = 'Language: English. Change language' if lang == 'en' else 'Sprache: Deutsch. Sprache wechseln'
    cur_en = ' aria-current="true"' if lang == 'en' else ''
    cur_de = ' aria-current="true"' if lang == 'de' else ''
    return (f'<details class="lang-switch">'
            f'<summary class="lang-switch-toggle" aria-label="{label}" title="{label}">{GLOBE}</summary>'
            f'<ul class="lang-switch-menu">'
            f'<li><a href="{en_href}" hreflang="en" lang="en" title="English"{cur_en}>EN</a></li>'
            f'<li><a href="{de_href}" hreflang="de" lang="de" title="Deutsch"{cur_de}>DE</a></li>'
            f'</ul></details>')


def alternates(en_path, de_path):
    en = DOMAIN + (pretty(en_path) if en_path != '/index.html' else '/')
    de = DOMAIN + pretty(de_path)
    return (f'<link rel="alternate" hreflang="en" href="{en}">\n'
            f'    <link rel="alternate" hreflang="de-CH" href="{de}">\n'
            f'    <link rel="alternate" hreflang="x-default" href="{en}">')


def translate_page(en_path, de_path, D, problems):
    soup = parse_en(en_path)
    soup.html['lang'] = 'de-CH'

    # head
    if soup.title and soup.title.string:
        soup.title.string = tr(soup.title.string, D, problems)
    for m in soup.find_all('meta'):
        key = m.get('name') or m.get('property')
        if key in META and m.get('content'):
            m['content'] = tr(m['content'], D, problems)
        elif key == 'og:url':
            m['content'] = DOMAIN + pretty(de_path)
        elif key == 'og:locale':
            m['content'] = 'de_CH'
        elif key == 'og:locale:alternate':
            m['content'] = 'en_US'
    for l in soup.find_all('link', rel='alternate'):
        if l.get('hreflang'):
            l.decompose()
    canon = soup.find('link', rel='canonical')
    if canon:
        canon['href'] = DOMAIN + pretty(de_path)
        canon.insert_after(BeautifulSoup('\n    ' + alternates(en_path, de_path), 'html.parser'))
    for s in soup.find_all('script', type='application/ld+json'):
        data = json.loads(s.string)

        def fix(o, key=None):
            if isinstance(o, dict):
                if 'inLanguage' in o:
                    o['inLanguage'] = 'de-CH'
                return {k: fix(v, k) for k, v in o.items()}
            if isinstance(o, list):
                return [fix(v, key) for v in o]
            if isinstance(o, str):
                if key in LD_URL_KEYS and o.startswith(DOMAIN) and '#' not in o and o.rstrip('/') != DOMAIN:
                    return map_url(o, en_path)
                if key in LD_KEYS and LETTER.search(o) and not re.match(r'(https?:|mailto:)', o):
                    return tr(o, D, problems)
            return o
        s.string = '\n' + json.dumps(fix(data), ensure_ascii=False, indent=2) + '\n'

    # body text
    found = []
    walk(soup.body, found)
    for kind, node in found:
        if kind == 'text':
            raw = str(node)
            de = tr(raw, D, problems)
            lead = raw[:len(raw) - len(raw.lstrip())]
            trail = raw[len(raw.rstrip()):]
            node.replace_with(NavigableString(lead + de + trail))
        else:
            en, tags = serialize(node)
            if sid(en) not in D:
                problems.append(f'missing {sid(en)}: {en[:80]}')
                continue
            de = tr(en, D, problems)
            if sorted(PH.findall(de)) != sorted(PH.findall(en)):
                problems.append(f'placeholder mismatch {sid(en)}: {de[:80]}')
                continue
            frag = restore_tags(de, tags)
            node.clear()
            for c in list(BeautifulSoup(frag, 'html.parser').contents):
                node.append(c)
    for t in soup.body.find_all(True):
        if t.name in SKIP or skipped(t):
            continue
        for a in ATTRS:
            if t.get(a) and LETTER.search(t[a]):
                t[a] = tr(t[a], D, problems)
        if t.name == 'input' and t.get('name') == 'subject' and t.get('value'):
            t['value'] = tr(t['value'], D, problems)
        if t.name == 'input' and t.get('name') == 'redirect' and t.get('value'):
            t['value'] = map_url(t['value'], en_path)

    # links and assets
    for t in soup.find_all(True):
        for a in ('href', 'src', 'action', 'poster', 'data-src'):
            if t.get(a) and not (t.name == 'link' and t.get('rel') in (['canonical'], ['alternate'])):
                t[a] = map_url(t[a], en_path)
        if t.get('srcset'):
            t['srcset'] = map_srcset(t['srcset'], en_path)

    out = soup.decode(formatter=FMT)
    out = patch_common(out, en_path, de_path, 'de')
    return out


def restore_tags(de, tags):
    def rep(m):
        close, i, void = m.group(1), int(m.group(2)), m.group(3)
        t = tags[i]
        if close:
            return f'</{t.name}>'
        attrs = ''.join(f' {k}="{html.escape(" ".join(v) if isinstance(v, list) else v)}"'
                        for k, v in t.attrs.items())
        return f'<{t.name}{attrs}>'
    return PH.sub(rep, de)


# ---------------------------------------------------------------- string patches

NAV_UL = re.compile(r'<ul class="nav-menu">.*?</ul>', re.S)
OLD_SWITCH = re.compile(r'\n?[ \t]*<nav class="language-switch"[^>]*>.*?</nav>', re.S)
SWITCH = re.compile(r'\n?[ \t]*<details class="lang-switch">.*?</details>', re.S)


def patch_common(text, en_path, de_path, lang):
    """Switcher, stylesheet, script version. Works on raw HTML so English files keep their formatting."""
    text = SWITCH.sub('', text)
    text = OLD_SWITCH.sub('', text)
    m = NAV_UL.search(text)
    if m:
        text = text[:m.end()] + '\n            ' + switcher(en_path, de_path, lang) + text[m.end():]
    if m and 'lang-switch.css' not in text:
        depth = norm_path(en_path if lang == 'en' else de_path).count('/') - 1
        href = '../' * depth + 'css/lang-switch.css?v=1'
        text, n = re.subn(r'(\n(\s*)<link rel="stylesheet" href="[^"]*theme\.css[^"]*">)',
                          lambda mm: f'{mm.group(1)}\n{mm.group(2)}<link rel="stylesheet" href="{href}">', text, count=1)
        if not n:
            text = text.replace('</head>', f'    <link rel="stylesheet" href="{href}">\n</head>', 1)
    text = re.sub(r'(js/main\.js)\?v=\d+', r'\1?v=4', text)
    return text


def patch_english(en_path, de_path):
    f = file_of(en_path)
    text = f.read_text()
    new = patch_common(text, en_path, de_path, 'en')
    if 'rel="alternate" hreflang' not in new:
        new, _ = re.subn(r'(\n(\s*)<link rel="canonical" href="[^"]*">)',
                         lambda m: m.group(1) + '\n' + m.group(2) + alternates(en_path, de_path).replace('\n    ', '\n' + m.group(2)),
                         new, count=1)
    if new != text:
        f.write_text(new)
        return True
    return False


def patch_existing_german(en_path, de_path, D, problems):
    """Hand-written German page: shared German menu, switcher, links to German twins."""
    f = file_of(de_path)
    text = SWITCH.sub('', f.read_text())
    en_soup = parse_en(en_path)
    ul = en_soup.find('ul', class_='nav-menu')
    nav = None
    if ul:
        ul = copy.copy(ul)
        frag = BeautifulSoup(str(ul), 'html.parser')
        for a in frag.find_all('a'):
            a.string = tr(a.get_text(), D, problems)
            a['href'] = map_url(a['href'], en_path)
            if a['href'] == pretty(de_path):
                a['class'] = ['active']
            elif a.get('class'):
                del a['class']
        nav = frag.decode(formatter=FMT)
    if nav and NAV_UL.search(text):
        text = NAV_UL.sub(lambda m: nav, text, count=1)

    def link(m):
        url = m.group(2)
        # resolve the hand-written page's link from its own location
        mapped = map_url_from(url, de_path)
        return f'{m.group(1)}"{mapped}"'
    text = re.sub(r'(<a\b[^>]*?\bhref=)"([^"]*)"', link, text)
    text = patch_common(text, en_path, de_path, 'de')
    f.write_text(text)


def map_url_from(url, page):
    """Link on a German page: point English pages that have a German twin to the twin."""
    if not url or url.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:')):
        return url
    parts = urlsplit(url)
    if parts.scheme in ('http', 'https'):
        return map_url(url, page)
    if parts.scheme:
        return url
    base = posixpath.dirname(norm_path(page))
    path = parts.path if parts.path.startswith('/') else posixpath.normpath(posixpath.join(base, parts.path))
    if parts.path.endswith('/') and not path.endswith('/'):
        path += '/'
    target = norm_path(path)
    if target in PAGES and norm_path(PAGES[target]) != norm_path(page):
        return urlunsplit(('', '', pretty(PAGES[target]), parts.query, parts.fragment))
    return url


# ---------------------------------------------------------------- commands

def extract():
    D = load_dict()
    todo, total = [], 0
    for en_path, de_path in PAGES.items():
        if norm_path(de_path) in EXISTING:
            soup = parse_en(en_path)
            ul = soup.find('ul', class_='nav-menu')
            items = [(sid(squash(a.get_text())), squash(a.get_text())) for a in ul.find_all('a')] if ul else []
        else:
            items = collect(parse_en(en_path))
        miss = [(i, s) for i, s in items if i not in D]
        total += len(miss)
        if miss:
            todo.append(f'### {en_path} -> {de_path}')
            todo += [f'{i}\t{s}' for i, s in miss]
    (ROOT / 'i18n/todo.txt').write_text('\n'.join(todo) + '\n')
    print(f'{total} strings without German -> i18n/todo.txt')


def build():
    D = load_dict()
    problems = []
    for en_path, de_path in PAGES.items():
        de_path = norm_path(de_path)
        if de_path in EXISTING:
            patch_existing_german(en_path, de_path, D, problems)
        else:
            out = translate_page(en_path, de_path, D, problems)
            file_of(de_path).parent.mkdir(parents=True, exist_ok=True)
            file_of(de_path).write_text(out)
        patch_english(en_path, de_path)
    if problems:
        print('\n'.join(sorted(set(problems))))
        print(f'{len(set(problems))} problems')
        sys.exit(1)
    print('built', len(PAGES), 'page pairs')


if __name__ == '__main__':
    {'extract': extract, 'build': build}[sys.argv[1] if len(sys.argv) > 1 else 'build']()
