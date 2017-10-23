#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import markdown
import git
import mimetypes
import configparser
import os
import cgi

REPO = None
TITLE = None

htmlHeader = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
<div style="border: 1px solid gray">
<h1>%s</h1>
%s
</div>
"""

htmlFooter = "</body></html>"

pageTemplate = htmlHeader + """
%s
""" + htmlFooter

editTemplate = htmlHeader + """
<form action="%s" method="post" id="foo">
<textarea style="width:100%%;height:500px" name="content">
%s
</textarea>
<button type="submit">Save</button>
</form>
""" + htmlFooter

class HTTPServer_RequestHandler(BaseHTTPRequestHandler):
    repo = None

    def getContentsFromGit(self, path):
        return self.repo.git.show("HEAD:" + path, stdout_as_string=False)

    def renderHTML(self, contents):
        return markdown.markdown(contents.decode('utf8'))

    def initRepo(self):
        if not self.repo:
            self.repo = git.Repo(REPO)

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

        if self.repo.bare:
            self.send_response(403)
            self.end_headers()
            return

        path = self.path
        if path.startswith('/'):
            path = path[1:]

        form = cgi.FieldStorage(fp = self.rfile, headers = self.headers,
                environ={'REQUEST_METHOD':'POST',
                         'CONTENT_TYPE':self.headers['Content-Type'],
                     })

        if "content" in form:
            with open(REPO + "/" + path, "wb") as f:
                f.write(form.getvalue('content').encode('utf8'))

        self.repo.index.add([path])
        self.repo.index.commit("Commit message", author=git.Actor("Author name", "author@example.com"), committer=git.Actor("Committer name", "committer@example.com"))

        self.do_GET()
        return

    def do_GET(self):
        pageControls = ""
        editRequest = False

        self.initRepo()

        path = self.path
        if path.startswith('/'):
            path = path[1:]

        if path.endswith('?edit'):
            path = path[:-5]
            editRequest = True

        if not editRequest and not self.repo.bare:
            pageControls = '<a href="%s?edit">Edit</a>' % path

        try:
            text = self.getContentsFromGit(path)
        except Exception as e:
            self.send_response(404)
            self.end_headers()
            print(e)
            return

        contentType, encoding = mimetypes.guess_type(path)
        if not contentType:
            if editRequest:
                text = (editTemplate % (TITLE, pageControls, path, text.decode('utf8'))).encode('utf8')
            else:
                text = (pageTemplate % (TITLE, pageControls, self.renderHTML(text))).encode('utf8')

            contentType == 'text/html'

        self.send_response(200)
        self.send_header('Content-type', contentType)
        self.end_headers()
        self.wfile.write(text)
        return

config = configparser.ConfigParser()
config.read('wiki.conf')
REPO = config.get('Wiki', 'Repository')
TITLE = config.get('Wiki', 'Title')
assert(os.path.exists(REPO))
print("Using repository at", REPO)

server_address = ('127.0.0.1', 8080)
httpd = HTTPServer(server_address, HTTPServer_RequestHandler)
print('running server...')
httpd.serve_forever()
