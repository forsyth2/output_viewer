from xml.etree.ElementTree import TreeBuilder, tostring, XMLParser
import os


class TreeProxy(object):
    """Used to auto-close tags from bad HTML sources"""
    def __init__(self, real_builder):
        self.builder = real_builder
        self.open = []

    def start(self, tagname, attrs):
        self.open.append(tagname)
        self.builder.start(tagname, attrs)

    def end(self, tagname):
        if tagname not in self.open:
            raise ValueError("Can't close tag '%s'; no open tag found.")
        while tagname != self.open[-1]:
            # Close all of the tags that are open that should have been closed.
            self.builder.end(self.open.pop())
        self.open.pop()
        self.builder.end(tagname)

    def cleanup(self):
        while self.open:
            self.builder.end(self.open.pop())

    def data(self, data):
        self.builder.data(data)

    def close(self):
        return self.builder.close()


class HTMLBuilder(object):
    def __init__(self, tagname="div", **attrs):
        self.children = []
        self._formatted = []
        # Allow things like "class_" to be normalized to "class"
        self._attrs = attrs
        self._tagname = tagname

    def append(self, child):
        self.children.append(child)

    def append_tag(self, tagname, **attrs):
        tag = HTMLBuilder(tagname=tagname, **attrs)
        self.append(tag)
        return tag

    def append_formatted(self, formatted_text):
        # We'll use an XML parser to feed the TreeBuilder when we get to this index
        self._formatted.append(len(self.children))
        self.children.append(formatted_text)

    def find(self, tagname):
        matches = []
        for c in self.children:
            if isinstance(c, HTMLBuilder):
                if c.tagname() == tagname:
                    matches.append(c)
                matches = matches + c.find(tagname)
        return matches

    def tagname(self):
        return self._tagname

    def attrs(self):
        clean_attrs = {}
        for attr, value in self._attrs.items():
            attr = attr.strip("_")
            if isinstance(value, dict):
                for k in value:
                    clean_attrs["%s-%s" % (attr, k)] = value[k]
            else:
                clean_attrs[attr] = value
        return clean_attrs

    def build(self, root=None):
        if root is None:
            was_root = True
            root = TreeBuilder()
        else:
            was_root = False

        root.start(self.tagname(), self.attrs())
        for i, child in enumerate(self.children):
            if isinstance(child, HTMLBuilder):
                child.build(root=root)
            else:
                if i in self._formatted:
                    try:
                        proxy = TreeProxy(root)
                        parser = XMLParser(html=True, target=proxy)
                        parser.feed(child)
                        proxy.cleanup()
                    except Exception as e:
                        print("Bad formatting", e)
                        root.data(str(child))
                else:
                    root.data(str(child))
        root.end(self.tagname())

        if was_root:
            root = root.close()
            return str(tostring(root, method="html").decode('utf-8'))


class Document(HTMLBuilder):
    def __init__(self, title=None, level=0):
        # Adjust for nesting level
        self._scripts = []
        for script in ["jquery-2.2.3.min.js", "bootstrap.min.js", "viewer.js"]:
            self._scripts.append(os.path.join(*([".."] * level + ["viewer", "js", script])))

        self._stylesheets = []
        for sheet in ["bootstrap.min.css", "viewer.css"]:
            self._stylesheets.append(os.path.join(*([".."] * level + ["viewer", "css", sheet])))

        self._metas = [{"name": "viewport", "content": "width=device-width, intial-scale=1"}, {"charset": "utf-8"}]
        self.children = []
        self._formatted = []
        self._attrs = {}
        self.title = title

    def tagname(self):
        return "body"

    def append_script(self, path):
        self._scripts.append(path)

    def append_style(self, path):
        self._stylesheets.append(path)

    def append_meta(self, attrs):
        self._metas.append(attrs)

    def build(self, root=None):
        if root is None:
            root = TreeBuilder()
            root.start("html", {})
            root.start("head", {})
            if self.title:
                root.start("title", {})
                root.data(self.title)
                root.end("title")
            for meta in self._metas:
                root.start("meta", meta)
                root.end("meta")
            for style in self._stylesheets:
                root.start("link", {"rel": "stylesheet", "href": style, "type": "text/css"})
                root.end("link")
            for script in self._scripts:
                root.start("script", {"type": "text/javascript", "src": script})
                root.data(" ")
                root.end('script')
            root.end("head")
        super(Document, self).build(root=root)
        root.end("html")
        root = root.close()
        return "<!DOCTYPE html>\n%s" % str(tostring(root, method="html").decode('utf-8'))


class TableCell(HTMLBuilder):
    def tagname(self):
        return 'td'


class TableHeader(HTMLBuilder):
    def tagname(self):
        return "th"


class TableRow(HTMLBuilder):
    def tagname(self):
        return "tr"

    def append_cell(self, child, **attrs):
        cell = TableCell(**attrs)
        cell.append(child)
        self.append(cell)


class HeaderRow(TableRow):
    def append_cell(self, child, **attrs):
        cell = TableHeader(**attrs)
        cell.append(child)
        self.append(cell)


class Table(HTMLBuilder):
    def tagname(self):
        return "table"

    def append_row(self, **attrs):
        row = TableRow(**attrs)
        self.append(row)
        return row

    def append_header(self, **attrs):
        row = HeaderRow(**attrs)
        self.append(row)
        return row


class Link(HTMLBuilder):
    def tagname(self):
        return "a"


class Span(HTMLBuilder):
    def tagname(self):
        return "span"


class BootstrapDropdown(HTMLBuilder):
    def __init__(self, name, links):
        super(BootstrapDropdown, self).__init__(class_="dropdown")
        outer_link = self.append_tag("a", href="#", class_="dropdown-toggle", data={"toggle": "dropdown"}, aria={"haspopup":"true", "expanded": "false"}, role="button")
        outer_link.append(name)
        outer_link.append_tag("span", class_="caret")

        ul = self.append_tag("ul", class_="dropdown-menu")
        for link_name in links:
            li = ul.append_tag("li")
            a = Link(href=links[link_name])
            a.append(link_name)
            li.append(a)

    def tagname(self):
        return "li"


class BootstrapNavbar(HTMLBuilder):
    def __init__(self, brand, root, links, **attrs):
        attrs.update({"class_": "navbar navbar-default"})
        super(BootstrapNavbar, self).__init__(**attrs)
        container = self.append_tag("div", class_="container-fluid")
        brand_link = container.append_tag("a", class_="navbar-brand", href=root)
        brand_link.append(brand)
        navbar_links = container.append_tag("ul", class_="nav navbar-nav")
        for link in links:
            if isinstance(links[link], dict):
                if len(links[link]) == 0:
                    continue
                elif len(links[link]) == 1:
                    title, url = list(links[link].items())[0]
                    li = navbar_links.append_tag("li")
                    a = li.append_tag("a", href=url)
                    a.append(title)
                else:
                    li = BootstrapDropdown(link, links[link])
                    navbar_links.append(li)
            else:
                li = navbar_links.append_tag("li")
                a = li.append_tag("a", href=links[link])
                a.append(link)

    def setLevel(self, level):
        links = self.find("a")
        for l in links:
            if "href" in l._attrs and l._attrs["href"][0] != "/":
                # Remove all leading "../"
                parts = l._attrs["href"].split("/")
                filtered = []
                for p in parts:
                    # Only remove the leading ones...
                    if p == ".." and len(filtered) == 0:
                        continue
                    filtered.append(p)

                l._attrs["href"] = os.path.join(*([".."] * level + filtered))

    def tagname(self):
        return "nav"
