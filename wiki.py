#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import markdown
import git
import mimetypes
import configparser
import os
import cgi
from urllib.parse import urlparse

class HTTPServer_RequestHandler(BaseHTTPRequestHandler):
    repo = None

    def getContentsFromGit(self, path):
        return self.repo.git.show("HEAD:" + path, stdout_as_string=False)

    def renderHTML(self, contents):
        return markdown.markdown(contents.decode('utf8'), extensions=['markdown.extensions.tables', 'markdown.extensions.toc'])

    def initRepo(self):
        if not self.repo:
            self.repo = git.Repo(config.get('Wiki', 'Repository'))

    def validatedPath(self):
        url = urlparse(self.path)
        path = url.path[1:]

        if len(path) == 0:
            path = config.get("Wiki", "DefaultPage", fallback="index.md")

        return (url, path)

    def searchRepo(self, expression):
        result = []
        gitOutput = []
        self.initRepo()

        try:
            gitOutput = self.repo.git.grep(['-i', '--', expression, 'HEAD']).split('\n')
        except:
            pass

        for line in gitOutput:
            line = line[line.find(':')+1:] # strip HEAD:
            filename = line[:line.find(':')]
            text = line[line.find(':')+1:]
            result.append({'filename': filename, 'text': text})
        return result

    def do_POST(self):
        self.initRepo()

        url, path = self.validatedPath()

        if self.repo.bare:
            self.send_response(403)
            self.end_headers()
            return

        form = cgi.FieldStorage(fp = self.rfile, headers = self.headers,
                environ={'REQUEST_METHOD':'POST',
                         'CONTENT_TYPE':self.headers['Content-Type'],
                     })

        if "textarea" in form:
            with open(config.get('Wiki', 'Repository') + "/" + path, "wb") as f:
                f.write(form.getvalue('textarea').encode('utf8'))

        self.repo.index.add([path])
        self.repo.index.commit("Commit message", author=git.Actor("Author name", "author@example.com"), committer=git.Actor("Committer name", "committer@example.com"))

        self.do_GET()
        return

    def do_GET(self):
        self.initRepo()
        template = None
        output = None
        stylesheets = ""

        url, path = self.validatedPath()

        try:
            output = self.getContentsFromGit(path)
        except Exception as e:
            template = "create"
            print(e)

        contentType, encoding = mimetypes.guess_type(path)

        if contentType and template == "create":
            self.send_response(404)
            self.end_headers()
            return

        if not template:
            if url.query == "edit":
                template = "edit"
            elif url.query.startswith("search="):
                template = "search"
            else:
                template = "view"

        if not contentType:
            content = None
            contentType == 'text/html'

            if template == 'edit':
                content = output.decode('utf8')
            elif template == "search":
                content = ''
                results = self.searchRepo(url.query[7:])
                if len(results):
                    content = content + "Search results for: " + url.query[7:]
                else:
                    content = content + "No results for: " + url.query[7:]

                for i in results:
                    content = content + ('<div><a href="%s"/>%s</a><div>%s</div></div>' % (i['filename'], i['filename'], i['text']))
            else:
                content = self.renderHTML(output)

            if self.repo.bare:
                stylesheets = stylesheets + "<style>.edit { display:none; }</style>"
            if config.has_option('Wiki', 'Stylesheet'):
                stylesheets = stylesheets + ('<link rel="stylesheet" type="text/css" href="%s" />' % config.get('Wiki', 'Stylesheet'))

            with open(template + ".html" , 'r') as f:
                output = f.read()
            output = output.replace("@EDIT_LINK@", url.path + "?edit")
            output = output.replace("@SAVE_LINK@", url.path)
            output = output.replace("@CONTENT@", content)
            output = output.replace("@TITLE@", config.get('Wiki', 'Title', fallback="<no title>"))
            output = output.replace("@STYLESHEETS@", stylesheets)
            output = output.encode('utf8')

        self.send_response(200)
        self.send_header('Content-type', contentType)
        self.end_headers()
        self.wfile.write(output)
        return

config = configparser.ConfigParser()
config.read('wiki.conf')

repo = config.get('Wiki', 'Repository')
assert(os.path.exists(repo))
print("Using repository at", repo)

httpd = HTTPServer(('127.0.0.1', 8080), HTTPServer_RequestHandler)
print('Running server...')
httpd.serve_forever()
