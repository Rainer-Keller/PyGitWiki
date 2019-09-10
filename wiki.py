#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from optparse import OptionParser
import markdown
import git
import mimetypes
import configparser
import os
import cgi
from urllib.parse import urlparse

def getRepositoryPath():
    return os.path.expanduser(config.get('Git', 'Repository'))

class HTTPServer_RequestHandler(BaseHTTPRequestHandler):
    repo = None
    dataDir = os.path.dirname(os.path.realpath(__file__))
    markdown = markdown.Markdown(extensions = ['markdown.extensions.tables',
                                               'markdown.extensions.toc',
                                               'markdown.extensions.meta',
                                              ])

    def getContentsFromGit(self, path):
        return self.repo.git.show("HEAD:" + path, stdout_as_string=False)

    def renderHTML(self, contents):
        return self.markdown.convert(contents.decode('utf8'))

    def initRepo(self):
        if not self.repo:
            gitrepo = getRepositoryPath()
            if not os.path.exists(gitrepo):
               self.repo = git.Repo.init(gitrepo)
            else:
               self.repo = git.Repo(gitrepo)

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

            newFilePath = os.path.join(getRepositoryPath(), path)
            os.makedirs(os.path.dirname(newFilePath), exist_ok=True)
            with open(newFilePath, "wb") as f:
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
            print(e)
            # Consider all failed git commands as 'not found'
            template = "notfound"
            encoding = contentType = None

        replacements["edit_link"] = url.path + "?edit"
        replacements["save_link"] = url.path
        replacements["title"] = config.get('Wiki', 'Title', fallback="<no title>")
        replacements["page_title"] = replacements["title"]

        if url.query == "stylesheet":
            contentType = 'text/css'
            with open(os.path.join(self.dataDir, "stylesheet.css"), 'rb') as f:
                output = f.read()

        if not contentType or contentType == 'text/markdown':
            # Mimetype text/markdown has to be converted to text/html
            content = None
            contentType = 'text/html'

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
                if 'title' in self.markdown.Meta:
                    replacements['title'] = self.markdown.Meta['title'][0]
                    replacements['page_title'] = replacements['title'] + ' - ' + replacements['page_title']

            if self.repo.bare:
                replacements['stylesheets'] = replacements.get('stylesheets', '') + "<style>.edit { display:none; }</style>"
            replacements['stylesheets'] = replacements.get('stylesheets', '') + ('<link rel="stylesheet" type="text/css" href="/%s" />' % config.get('Wiki', 'Stylesheet', fallback="?stylesheet"))

            with open(os.path.join(self.dataDir, template + ".html") , 'rb') as f:
                output = f.read()

            replacements['content'] = content
            for i in replacements:
                output = output.replace(("@" + i.upper() + "@").encode('utf8'), replacements[i].encode('utf8'))

        self.send_response(200)
        self.send_header('Content-type', contentType)
        self.end_headers()
        self.wfile.write(output)
        return

dataDir = os.path.dirname(os.path.realpath(__file__))
config = configparser.ConfigParser()

parser = OptionParser()
parser.add_option("-d", "--dataDir", action="store", dest="dataDir")
parser.add_option("-c", "--config", action="store", dest="config")
(options, args) = parser.parse_args()
if options.config:
    if not os.path.exists(options.config):
        raise Exception("Config '" + options.config + "' does not exist")
    print("Load configuration", options.config)
    config.read(options.config)
else:
    print("Load configuration", os.path.join(dataDir, 'wiki.systemconf'))
    config.read(os.path.join(dataDir, 'wiki.systemconf'))

userConfig = os.path.expanduser(config.get('System', 'userConfig', fallback=options.config))

if config.has_option('System', 'DataDir'):
    dataDir = config.get('System', 'DataDir')

if userConfig and not os.path.exists(userConfig):
    print("Starting new wiki...")
    os.makedirs(os.path.dirname(userConfig), exist_ok=True)
    with open(os.path.join(dataDir, 'wiki.conf.example')) as f:
        content = f.read()
    content = content.replace('Repository = /path/to/repository', "Repository = " + config.get('System', 'DefaultRepositoryPath'))
    with open(userConfig, 'w') as f:
        f.write(content)

print("Load configuration", userConfig)
config.read(userConfig)

if config.has_option('Wiki', 'DataDir'):
    dataDir = config.get('Wiki', 'DataDir')

if options.dataDir:
    dataDir = options.dataDir

if not os.path.exists(dataDir):
    raise Exception("Datadir '" + dataDir + "' does not exist")

HTTPServer_RequestHandler.dataDir = dataDir

print("Using repository at", getRepositoryPath())

httpd = HTTPServer(('127.0.0.1', int(config.get("Wiki", "Port", fallback=8080))), HTTPServer_RequestHandler)
print('Running server on port', httpd.server_port)
httpd.serve_forever()

