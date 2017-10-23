#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import markdown
import git
import mimetypes
import configparser
import os
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

    def searchRepo(self, expression):
        result = []
        self.initRepo()
        for line in self.repo.git.grep([expression, 'HEAD']).split('\n'):
            line = line[line.find(':')+1:] # strip HEAD:
            filename = line[:line.find(':')]
            text = line[line.find(':')+1:]
            result.append({'filename': filename, 'text': text})
        return result

    def do_POST(self):
        self.initRepo()

        url = urlparse(self.path)
        path = url.path[1:]

        if self.repo.bare or url.query != "commit":
            self.send_response(403)
            self.end_headers()
            return

        content = self.rfile.read(int(self.headers['Content-Length']))

        with open(config.get('Wiki', 'Repository') + "/" + path, "wb") as f:
            f.write(content)

        self.repo.index.add([path])
        self.repo.index.commit("Commit message", author=git.Actor("Author name", "author@example.com"), committer=git.Actor("Committer name", "committer@example.com"))

        self.do_GET()
        return

    def do_GET(self):
        self.initRepo()

        url = urlparse(self.path)
        path = url.path[1:]

        try:
            text = self.getContentsFromGit(path)
        except Exception as e:
            self.send_response(404)
            self.end_headers()
            print(e)
            return

        contentType, encoding = mimetypes.guess_type(path)
        if not contentType:
            if url.query == 'raw':
                contentType = 'text/plain'
            else:
                contentType == 'text/html'
                with open('wiki.html', 'r') as f:
                    template = f.read()
                    template = template.replace("@TITLE@", config.get('Wiki', 'Title'))
                    html = self.renderHTML(text)
                    if self.repo.bare:
                        html = '<script>document.getElementById("editButton").classList.add("hidden")</script>' + html
                    template = template.replace("@HTML_HERE@", html)
                    text = template.encode('utf8')

        self.send_response(200)
        self.send_header('Content-type', contentType)
        self.end_headers()
        self.wfile.write(text)
        return

config = configparser.ConfigParser()
config.read('wiki.conf')

repo = config.get('Wiki', 'Repository')
assert(os.path.exists(repo))
print("Using repository at", repo)

httpd = HTTPServer(('127.0.0.1', 8080), HTTPServer_RequestHandler)
print('Running server...')
httpd.serve_forever()