# -*- coding: utf-8 -*-
import re
import ssl
import os
import md5
import copy
import imghdr
import base64
from random import getrandbits

from bs4 import BeautifulSoup
from urllib2 import (HTTPError, URLError, Request, build_opener,
                     HTTPCookieProcessor, urlopen)
import cookielib

import logging
logger = logging.getLogger(__name__)


class UrlResolver(object):
    def __init__(self, url):
        self.__users_url = url

    @property
    def url(self):
        url = self.__users_url.strip('/')
        re_http = re.compile('http:\/\/|https:\/\/')
        http_match = re_http.match(url)
        if not http_match:
            url = "%s/%s" % ('http://', url)
        return url

    @property
    def domain(self):
        return self.url.split('/')[2]

    @property
    def path(self):
        return '/'.join(self.url.split('/')[0:3])

    def trim_url(self, url):
        return re.sub(r'(?:\/[\w\d\_\-]*)(?:\.html|\.htm|\.xml|\.php|\.css|\?.*|\#.*)(?:.*)',
                      '',
                      url)

    def normalize_url(self, original_url, parent=None):
        """
        This method:
            1. rstrips slashes
            2. converts directory changes in paths (`../`) to absolute paths
            3. returns both an HTTP and an HTTPS version of the URL in a tuple
        """
        re_http = re.compile('http:\/\/|https:\/\/|^\/\/|^\/')
        http_match = re_http.match(original_url)

        url = original_url.rstrip('/')

        if url.find('..') != -1:
            if parent:
                parent = '/'.join(parent.split('/')[:-(url.count('../')+1)])
                url = '%s/%s' % (parent, url.replace('../', ''))
            else:
                return self.normalize_url(url.replace('../', ''))
        elif http_match:
            if http_match.group(0) == '//':
                url = "%s%s" % ('http:', url)
            if http_match.group(0) == '/':
                url = "%s/%s" % (self.path, url.lstrip('/'))
        # If there is no protocol on the URL, this assumes it's a relative path
        # and will attempt to append it to the base URL.
        elif not http_match:
            url = "%s/%s" % (self.trim_url(self.url), url.lstrip('/'))
        # print 'final_url: ', url
        # print '------------------------'
        url_https = re.sub('http:\/\/|https:\/\/|^\/\/|^\/', 'https://', url)
        url = re.sub('http:\/\/|https:\/\/|^\/\/|^\/', 'http://', url)
        return url, url_https


class PageParser(object):

    def __init__(self, url, user_agent, directory):
        self.original_url = url
        self.urlResolver = UrlResolver(self.original_url)
        self.url = self.urlResolver.url
        self.user_agent = user_agent
        self.directory = directory
        self.protocol = 'https' if url.startswith('https') else 'http'

    def parse_page(self):
        page = self.read_url(self.original_url)

        soup = BeautifulSoup(page, "lxml")

        css = soup.find_all('link', {'rel': 'stylesheet'})
        js = soup.find_all('script')
        images = soup.find_all('img')
        styles = soup.find_all('style')
        inline_styles = soup.find_all(attrs={'style': re.compile(
            "(?:background|background-image):(?:[ ]+|)(?:[\#\w\d]*|)(?:[ ]+|)url\((.*?)\)")})

        formsDetection = FormsDetection(soup, self.url)
        formsDetection.replace()

        for i in images:
            if i.get('src'):
                i['src'] = self.parse_image(i['src'])
        for j in js:
            if j.get('src'):
                j['src'] = self.parse_javascript(j['src'])
                j['type'] = 'text/javascript'
        for _c in css:
            if _c.get('href'):
                _c['href'] = self.parse_css(_c['href'])
                _c['type'] = 'text/css'
        for s in styles:
            s.string = self.parse_css_text(s.string)
        for _is in inline_styles:
            _is.attrs['style'] = self.parse_css_text(_is.attrs['style'])

        return self.write_file(soup.encode_contents(), 'throwaway_dirname',
                               'html', 'w')

    def parse_css_text(self, source, parent=None):
        """Scan, save, and incorporate new links to external assets in CSS.

        Given a CSS blob (whether inlined or from a file), save all
        additional assets linked inside the file and replace the links with
        links to the saved assets. Acts recursively with parse_css.

        Args:
            source (str): Some CSS to scan and save dependencies of.
            parent (str, optional): A link to the parent URL of this CSS blob.
                Used for determining URLs for links to other files.

        Returns:
            A string containing the result of replacing all links in the
                original CSS with links to asset paths saved in the course of
                parsing the CSS text.
        """
        re_css = re.compile('(?:@import url\(|@import )(?:[\'\"])(.*)(?:[\'\"])',
                            flags=re.IGNORECASE)
        re_img = re.compile('(?:background|background-image):(?:[ ]+|)(?:[\#\w\d\-\_]*|)(?:[ ]+|)url\((.*?)\)',
                            flags=re.IGNORECASE)
        re_font = re.compile('(?:\@font-face{)(?:[ \w\d\-\_\;\.\:\'\"]*)\(([ \w\d\-\_\;\.\:\'\"\/]*)\)',
                             flags=re.IGNORECASE)
        css_fa = re_css.findall(source)
        img_fa = re_img.findall(source)
        fonts_fa = re_font.findall(source)

        try:
            for css in css_fa:
                source = source.replace(css, self.parse_css(css, parent))

            for font in fonts_fa:
                source = source.replace(font, self.parse_fonts(font, parent))

            for img in img_fa:
                source = source.replace(img, self.parse_image(img, parent))
        except UnicodeDecodeError:
            logger.error('132 Can\'t load css in %s' % self.url)

        return source

    def parse_css(self, original_css_url, parent=None):
        """Load a CSS file, scrape and rewrite its internal links, and save it.

        Args:
            original_css_url (str): The URL of the CSS resource to scrape.

        Returns:
            The URL of the saved CSS asset.
        """
        source = self.read_url(original_css_url, parent)
        if source:
            url, url_https = self.urlResolver.normalize_url(original_css_url)
            if self.protocol == 'http':
                css_url = url
            else:
                css_url = url_https

            # This call is the only way for parse_css_text, parse_css,
            # parse_image, and parse_fonts to obtain a `parent` argument.
            # Unlike the other parse_foo methods, the return value of this call
            # is an entire file worth of CSS source rather than a link.
            source = self.parse_css_text(source, css_url)

            filename = '%s.%s' % (md5.new(css_url).hexdigest(), 'css')
            return self.write_file(source, filename, 'css', 'w')
        else:
            return original_css_url

    def parse_fonts(self, font_src, parent=None):
        stripped_url = font_src.replace('\'', '').replace('"', '')
        font = self.read_url(stripped_url, parent)
        if font:
            filename = self.urlResolver.trim_url(font_src).split('/')[-1:][0]
            return self.write_file(font, filename, 'font', 'w')
        else:
            return font_src

    def parse_image(self, img_src, parent=None):
        # Media types do not map cleanly to media extensions. Using svg+xml as
        # a file extension works, at least in Chrome. Media type registry:
        # https://www.iana.org/assignments/media-types/media-types.xhtml#image
        re_base64 = re.compile('data:image\/([a-zA-Z0-9_+.-]+);(base64)')
        re_fa = re_base64.findall(img_src)
        if re_fa and re_fa[0][1] == 'base64':
            prefix_length = img_src.find('base64,') + 7
            b64_data = img_src[prefix_length:]
            return self.write_base64(b64_data, re_fa[0][0])
        stripped_url = img_src.replace('\'', '').replace('"', '')
        img = self.read_url(stripped_url, parent)
        if img:
            filename = md5.new(img_src).hexdigest()
            ext = imghdr.what(None, img)
            filename = "%s.%s" % (filename, ext)
            return self.write_file(img, filename, 'img', 'wb')
        else:
            return img_src

    def parse_javascript(self, js_url):
        source = self.read_url(js_url)
        if source:
            filename = '%s.%s' % (md5.new(js_url).hexdigest(), 'js')
            return self.write_file(source, filename, 'js', 'w')
        else:
            return js_url

    def read_url(self, original_url, parent=None):
        url, url_https = self.urlResolver.normalize_url(original_url, parent)
        cj = cookielib.CookieJar()
        if not self.user_agent:
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X'
                       ' 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko)'
                       ' Version/7.0.3 Safari/7046A194A'}
        else:
            headers = {'User-Agent': self.user_agent}
        opener = build_opener(HTTPCookieProcessor(cj))
        try:
            request = Request(url, None, headers)
            source = opener.open(request).read()
        # SSL errors can come in two forms.
        except (HTTPError, URLError):
            try:
                request = Request(url_https, None, headers)
                source = opener.open(request).read()
            except HTTPError as e:
                logger.error('249 HTTPError: Can\'t load %s: %s' % (url, e))
                return ''
            except URLError:
                try:
                    # Using urllib2.HTTPSHandler with this context, then
                    # passing the handler to build_opener, does not prevent
                    # certificate verification failure. This does.
                    context = ssl._create_unverified_context()
                    request = Request(url_https, None, headers)
                    source = urlopen(request, context=context).read()
                except Exception as e:
                    logger.error('260 Except: Can\'t load %s: %s' % (url, e))
                    return ''
            except Exception as e:
                logger.error('263 Except: Can\'t load %s: %s' % (url, e))
                return ''
        except Exception as e:
            logger.error('266 Except: Can\'t load %s: %s' % (url, e))
            return ''
        return source

    def write_base64(self, base64_file, ext):
        try:
            imgdata = base64.b64decode(base64_file)
        except TypeError:
            padding = len(base64_file) % 4
            if padding == 1:
                logger.error("Invalid base64 string: {}".format(base64_file))
                return ''
            elif padding == 2:
                base64_file += b'=='
            elif padding == 3:
                base64_file += b'='
            imgdata = base64.b64decode(base64_file)
        filename = '%s.%s' % (md5.new(base64_file).hexdigest(), ext)
        return self.write_file(imgdata, filename, 'img', 'wb')

    def write_file(self, source, filename, filetype, mode):
        if filetype == 'html':
            filename = '%032x.html' % getrandbits(128)
        dest_dir = os.path.join(self.directory, filetype)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        try:
            with open('%s/%s' % (dest_dir, filename), mode) as f:
                f.write(source)
        except:
            logger.error('IOError [img]: Can\'t write %s' % filename)

        if filetype == 'html':
            return "%s/%s" % (dest_dir, filename)
        else:
            return "/%s/%s" % (dest_dir, filename)


class FormsDetection(object):
    def __init__(self, soup, url):
        self.soup = soup
        self.url = url

    def clearAttrs(self, el):
        if el and el.attrs:
            attrs = copy.copy(el.attrs)
            for attr in attrs:
                if attr != 'class':
                    del el[attr]

    def prepare(self, d_form, d_passwd, d_login):
        d_action = d_form.get('action', '')

        self.clearAttrs(d_form)
        self.clearAttrs(d_login)
        self.clearAttrs(d_passwd)

        d_login['name'] = 'sb_login'
        d_login['type'] = 'text'

        d_passwd['name'] = 'sb_password'
        d_passwd['type'] = 'password'

        d_form['act'] = d_action
        redirect_url = self.soup.new_tag("input", type='hidden',
                                         value=self.url)
        redirect_url['name'] = 'r'
        d_form.append(redirect_url)

        d_form['method'] = 'POST'
        d_form['action'] = '/'

        return d_form

    def detect(self):
        passwords = self.soup.find_all('input', {'type': 'password'})

        d_forms = []

        for pwd in passwords:
            d_login = pwd.find_all_previous('input',
                                            {'type': re.compile('text|email|username')})
            if d_login:
                d_login = d_login[-1]

            d_form = pwd.find_parent('form')

            d_form = self.prepare(d_form, pwd, d_login)

            d_forms.append(d_form)
        return d_forms

    def replace(self):
        forms = self.detect()
        for form in forms:
            old_form = self.soup.find('form', {'action': form['act']})
            old_form = form
        script = self.soup.new_tag('script', type='text/javascript')
        body = self.soup.find('body')
        body.append(script)
        script.string = '''NodeList.prototype.forEach = Array.prototype.forEach; NodeList.prototype.map = Array.prototype.map; var attributes, new_element; document.querySelectorAll("*").forEach(function(element){ attributes = Object.keys(element.attributes).map(function(key_index){ return element.attributes[key_index].nodeName }); attributes = attributes.filter(function(attribute){ if (typeof attribute !== "undefined") return 0 === attribute.toLowerCase().indexOf("on"); }); new_element = element.cloneNode(true); element.parentNode.replaceChild(new_element, element); attributes.forEach(function(attribute){ element.removeAttribute(attribute); });})'''
        return self.soup
