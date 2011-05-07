import os
from collections import namedtuple
from datetime import datetime

import jinja2
import yaml
import re
import isodate

import util
import renderers

class Page(object):
    """
    A single page on the website in all it's form, as well as it's
    associated metadata.
    """

    class Author(object):
        """Smartly manages a author with name and email"""
        parse_author_regex = re.compile(r'([^<>]*)( +<(.*@.*)>)$')

        def __init__(self, raw='', name=None, email=None):
            self.raw = raw
            self.name = name
            self.email = email

        @classmethod
        def parse(cls, raw):
            a = cls(raw)
            a.name, _, a.email = cls.parse_author_re.match(raw).groups()

        def __str__(self):
            if not name:
                return self.raw
            if not email:
                return name

            return "{0} <{1}>".format(name, email)

    def __init__(self, path, options, renderer=None):
        """
        Load a file from disk, and parse the metadata from it.

        Note that you still need to call `render` and `write` to do anything
        interesting.
        """
        self.header = None
        self.original = None
        self.parsed = None
        self.meta = {}
        self.options = options
        self.renderer = renderer if renderer else renderers.Plain
        self.subpages = []

        # TODO: It's not good to make a new environment every time, but we if
        # we pass the options in each time, its possible it will change per
        # instance. Fix this.
        self.tmpl_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                self.options.get('template_dir', 'templates')))

        self.path = path
        _, self.filename = os.path.split(path)

        with open(path) as f:
            self.original = f.read()
            # Maximum of one split, so --- in the content doesn't get split.
            splits = self.original.split('---', 1)

            # Handle the case where no meta data was provided
            if len(splits) == 1:
                self.meta = {}
                self.original = splits[0]
            else:
                header = splits[0]
                self.original = splits[1]
                self.meta = yaml.load(header)

        self.build_meta()

    def build_meta(self):
        """
        Ensures the gurantees about metadata for documents are valid.

        `page.title` - will exist.
        `page.slug` - will exist.
        `page.author` - will exist, and contain fields `name` and `email`.
        `page.category` - will exist, and be a list.
        `page.published` - will exist
        `page.datetime` - will exist
        """

        if not 'title' in self.meta:
            self.meta['title'] = '.'.join(self.filename.split('.')[:-1])
            if (self.meta['title'] == ''):
                self.meta['title'] = self.filename

            util.out.warn('metadata',
                "You didn't specify a title in  {0}. Using the file name as a title."
                .format(self.filename))
        # Gurantee: title exists.

        if not 'slug' in self.meta:
            self.meta['slug'] = util.slugify(self.meta['title'])
            util.out.debug('metadata',
                'You didn\'t specify a slug, generating it from the title.')
        elif self.meta['slug'] != util.slugify(self.meta['slug']):
            util.out.warn('metadata',
                'Your slug should probably be all lower case,' +
                'and match the regex "[a-z0-9-]*"')
        # Gurantee: slug exists.

        if 'author' in self.meta:
            self.meta['author'] = Page.parse(author)
        else:
            self.meta['author'] = Page.Author()
        # Gurantee: author exists.

        if 'category' in self.meta:
            self.meta['category'] = self.meta['category'].split('/')
        else:
            self.meta['category'] = []
        # Gurantee: category exists

        if not 'published' in self.meta:
            self.meta['published'] = True
        # Gurantee: published exists

        datetime_name=None
        for name in ['time', 'date', 'datetime']:
            if name in self.meta:
                datetime_name = 'date'
        if datetime_name:
            self.meta['datetime'] = isodate.parse_datetime(self.meta[datetime_name])
        else:
            self.meta['datetime'] = datetime.now()
        # Gurantee: datetime exists

    def render(self):
        """
        Renders the page to full html.

        First parse the content, then build a set of variables for the
        template, finally render it with jinja2.
        """

        self.content = self.renderer.render(self.original)

        type = self.meta.get('type', 'default')
        template = self.tmpl_env.get_template(type + '.html')
        templ_vars = {
            'page': self,
            'site': {
                'title': self.options.get('site_title', 'Untitled'),
                'datetime': datetime.now(),
            },
        }
        self.html = template.render(templ_vars)

    def write(self, dir=None):
        """Write the page to an html file on disk."""

        # Use what we are passed, or the default given, or the current dir
        if not dir:
            dir = self.options.get('output_dir', '.')

        path = os.path.join(dir, self.slug + '.html')
        with open(path, 'w') as f:
            f.write(self.html)

    # Make the public interface ignore the seperation between the meta
    # dictionary and the properies of the Page object.
    def __getattr__(self, name):
        if name in self.meta:
            return self.meta[name]
