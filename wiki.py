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
            self.repo = git.Repo(config.get('Git', 'Repository'))

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

        try:
            filecontent = b''
            if "textarea" in form:
                filecontent = form.getvalue('textarea').encode('utf8')

            os.makedirs(os.path.dirname(config.get('Git', 'Repository') + "/" + path), exist_ok=True)
            with open(config.get('Git', 'Repository') + "/" + path, "wb") as f:
                f.write(filecontent)

            self.repo.index.add([path])
            gitUser = git.Actor(config.get("Git", "User.Name", fallback="Wiki"), config.get("Git", "User.Email", fallback="wiki@localhost"))
            commitMessage = form.getvalue('commitMessage')
            if not commitMessage:
                commitMessage = "No commit message"
            self.repo.index.commit(commitMessage, author=gitUser, committer=gitUser)
        except Exception as e:
            print(e)
            self.send_response(403)
            self.end_headers()
            return

        self.do_GET()
        return

    def do_GET(self):
        self.initRepo()
        template = None
        output = None
        replacements = {}

        url, path = self.validatedPath()
        contentType, encoding = mimetypes.guess_type(path)

        try:
            output = self.getContentsFromGit(path)
        except Exception as e:
            if contentType:
                self.send_response(404)
                self.end_headers()
                return
            else:
                template = "notfound"

        replacements["edit_link"] = url.path + "?edit"
        replacements["save_link"] = url.path
        replacements["title"] = config.get('Wiki', 'Title', fallback="<no title>")

        if not contentType:
            content = None
            contentType == 'text/html'

            if template == "notfound" and url.query == "create":
                template = "edit"
                content = ''
            elif url.query == "edit":
                template = "edit"
                content = output.decode('utf8')
            elif url.query.startswith("search="):
                template = "search"
                content = ''
                results = self.searchRepo(url.query[7:])
                if len(results):
                    content = content + "Search results for: " + url.query[7:]
                else:
                    content = content + "No results for: " + url.query[7:]

                for i in results:
                    content = content + ('<div><a href="%s"/>%s</a><div>%s</div></div>' % (i['filename'], i['filename'], i['text']))
            elif template == "notfound":
                    content = "This page does not exist"
                    replacements["edit_link"] = url.path + "?create"
            else:
                template = 'view'
                content = self.renderHTML(output)

            if self.repo.bare:
                replacements['stylesheets'] = replacements.get('stylesheets', '') + "<style>.edit { display:none; }</style>"
            if config.has_option('Wiki', 'Stylesheet'):
                replacements['stylesheets'] = replacements.get('stylesheets', '') + ('<link rel="stylesheet" type="text/css" href="/%s" />' % config.get('Wiki', 'Stylesheet'))

            with open(template + ".html" , 'rb') as f:
                output = f.read()

            replacements['content'] = content
            for i in replacements:
                output = output.replace(("@" + i.upper() + "@").encode('utf8'), replacements[i].encode('utf8'))

        self.send_response(200)
        self.send_header('Content-type', contentType)
        self.end_headers()
        self.wfile.write(output)
        return

config = configparser.ConfigParser()
config.read('wiki.conf')

repo = config.get('Git', 'Repository')
assert(os.path.exists(repo))
print("Using repository at", repo)

httpd = HTTPServer(('127.0.0.1', 8080), HTTPServer_RequestHandler)
print('Running server...')
httpd.serve_forever()
