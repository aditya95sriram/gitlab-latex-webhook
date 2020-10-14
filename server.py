#!/usr/bin/python3.6

# author: P. R. Vaidyanathan
# github: aditya95sriram
# python: 3.6+
# requires: cloud_mkdir.sh, cloud_upload.sh
#
# Python server to listen to gitlab webhooks and compile latex files
# specified in query params, and upload to owncloud


import http.server  # to subclass BaseHTTPServer
from http import HTTPStatus  # list of HTTP status codes
import socketserver  # basic TCP server, does most of request handling
from urllib.parse import urlparse, parse_qsl  # to parse query params
import json  # to parse request body
import subprocess  # to run shell scripts for compiling tex and uploading to owncloud
import os  # for os.path
import shutil  # to delete entire directory using rmtree
from datetime import datetime  # for informative logging
import signal  # for signal.alarm and timely fallback response

from time import sleep  # for testing
from pprint import pprint  # for pretty printing

PORT = 3838  # port on which server listens to request
SECRET_TOKEN = os.environ.get("GITLAB_SECRET_TOKEN")  # secret gitlab token for verifying
REPO_PREFIX = "repo-"  # prefix of local directory where repo is cloned
DEFAULT_COMMAND_ARGS = {"pdflatex": ["-interaction=nonstopmode"]}
DEFAULT_LATEX_COMMANDS = ("pdflatex", "bibtex", "pdflatex", "pdflatex")


# modify print function to log timestamp
old_print = print
def print(*args, **kwargs):
    timestamp = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    old_print(f"[{timestamp}]", *args, **kwargs)


def run_latex(directory, file, commands=DEFAULT_LATEX_COMMANDS):
    # todo: make run_latex a generator so that all the logs are
    #       communicated back as soon as possible
    base, ext = os.path.splitext(os.path.basename(file))
    failed = False
    failout = failerr = ""
    for command in commands:
        args = DEFAULT_COMMAND_ARGS.get(command, [])
        final_command = [command] + args + [base]
        print("running command:", " ".join(final_command))
        proc = subprocess.run(final_command, cwd=directory, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        if proc.returncode != 0:
            print(f"detected errors, returncode: {proc.returncode}")
            failed = True
            failout += f"\n{command}:" + proc.stdout
            failerr += f"\n{command}:" + proc.stderr
    return failed, failout, failerr


class BuildRequestHandler(http.server.BaseHTTPRequestHandler):

    def abort(self, message="error", statuscode=HTTPStatus.INTERNAL_SERVER_ERROR):
        self.send_response(statuscode)
        self.send_header("x-message", message)
        self.send_header("content-type", "text/plain")
        self.end_headers()
        self.headers_sent = True

    def send_build_log(self, intermediate=False):
        response_body = []
        if self.build_failed:
            response_body += ["# Build Log", "## stdout:", self.failout,
                              "## stderr:", self.failerr]
        else:
            response_body += ["# Build Log",
                              "no build errors" + intermediate*" so far"]
        response_body += ["-" * 40, ""]
        if self.upload_failed:
            response_body += ["# Upload Log", "## stdout:", self.ufailout]
        else:
            response_body += ["# Upload Log",
                              "no upload errors" + intermediate*" so far"]
        self.wfile.write("\n".join(response_body).encode())

    def do_POST(self):
        client_address, client_port = self.client_address
        print(f"received request from {client_address}:{client_port}")

        # additional instance variables for reporting purposes
        self.job_status = "initializing"
        self.build_failed = False
        self.failout = self.failerr = ""
        self.upload_failed = False
        self.ufailout = ""
        self.headers_sent = False

        # set fallback responder
        def alarm_handler(signalnum, frame):
            print("alarm signalled, sending current status:", self.job_status)
            self.abort(f"job not finished yet, status: {self.job_status}",
                       HTTPStatus.ACCEPTED)
            self.send_build_log(intermediate=True)
            MainServer.shutdown_request(self.request)
            print("shutting down request, no more reporting possible")

        signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(9)

        # process headers

        # verify secret token
        secret_token = self.headers.get("x-gitlab-token", None)
        if SECRET_TOKEN is not None and secret_token != SECRET_TOKEN:
            print("invalid secret token")
            return self.abort("invalid secret token", HTTPStatus.FORBIDDEN)

        # verify gitlab event type
        gitlab_event = self.headers.get("x-gitlab-event", None)
        if gitlab_event != "Push Hook":
            print("invalid gitlab event")
            return self.abort(f"only 'Push Hook' supported, not '{gitlab_event}'",
                              HTTPStatus.BAD_REQUEST)

        # process url params
        parsed_url = urlparse(self.path)
        params = dict(parse_qsl(parsed_url.query))
        filestr = params.get("files", "")
        files = filestr.split(",")
        print("files to process:", files)

        # read body
        if 'Content-Length' in self.headers:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length).decode()
        else:
            body = self.rfile.read().decode()
        data = json.loads(body)
        # print("got data:")
        # pprint(data)
        repo_name = data['project'].get('name')
        repo_path = REPO_PREFIX + repo_name
        print("repo name:", repo_name)
        git_ssh_url = data['project'].get('git_ssh_url', None)
        print("git url:", git_ssh_url)

        # clear repo directory if it already exists
        if os.path.isdir(repo_path):
            print("directory already exists")
            try:
                shutil.rmtree(repo_path)
            except Exception as err:
                print("error while deleting repo")
                print("error message:", err)
                return self.abort(f"unable to delete existing repo directory: {err}")
            else:
                print("removed existing directory")

        # clone repo
        try:
            subprocess.check_output(["git", "clone", git_ssh_url, repo_path],
                                    stderr=subprocess.STDOUT, universal_newlines=True)
        except subprocess.CalledProcessError as err:
            print("error while cloning")
            print("trace:", err.stdout)
            return self.abort(f"error while git cloning, trace:\n{err.stdout}")
        else:
            self.job_status = "cloned repo"
            print("cloned successfully")

        # run latex
        for file in files:
            failed, failout, failerr = run_latex(repo_path, file)
            if failed:
                print("detected error while compiling", file)
                print("stdout:", failout)
                print("stderr:", failerr)
                self.build_failed = True
                self.failout += f"\n### {file}:\n" + failout
                self.failerr += f"\n### {file}:\n" + failerr
                # return self.abort(f"error while compiling {file}, trace:\n{err.stdout}")
            else:
                print(file, "built successfully")
        self.job_status += ". build completed"
        if self.build_failed: self.job_status += " with tex errors"

        # uploading phase
        # prepare owncloud folder to upload in
        try:
            subprocess.check_output(["bash", "cloud_mkdir.sh", repo_name],
                                    stderr=subprocess.STDOUT,
                                    universal_newlines=True)
        except subprocess.CalledProcessError as err:
            print("error while creating owncloud directory")
            print("trace:", err.stdout)
            self.upload_failed = True
            self.ufailout = err.stdout
        else:
            self.job_status += ". owncloud folder created"
            print("owncloud folder created or already exists")

        # upload files to prepared folder
        if not self.upload_failed:
            for file in files:
                base, ext = os.path.splitext(os.path.basename(file))
                pdf = f"{base}.pdf"
                srcpath = f"repo/{pdf}"
                destpath = f"{repo_name}/{pdf}"
                try:
                    subprocess.check_output(["bash", "cloud_upload.sh",
                                             destpath, srcpath],
                                            stderr=subprocess.STDOUT,
                                            universal_newlines=True)
                except subprocess.CalledProcessError as err:
                    print(f"error while uploading {pdf}")
                    print("trace:", err.stdout)
                    self.ufailout += err.stdout + "\n\n"
                    self.upload_failed = True
                    # uncomment following to stop on first failed upload
                    # if not self.headers_sent:
                    #     self.abort(f"error while uploading {pdf}")
                    #     self.send_build_log()
                    #     return
                else:
                    print(f"successfully uploaded {pdf}")
            self.job_status += ". files uploaded to owncloud "

        # send dummy success response,
        # response body contains more details and potential error logs
        if not self.headers_sent:
            self.send_response(HTTPStatus.OK)
            self.send_header("x-message", self.job_status)
            self.end_headers()
            # send build log as body
            self.send_build_log()

        signal.alarm(0)  # processing done, disable the alarm

        # clean up
        if os.path.isdir(repo_path):
            shutil.rmtree(repo_path)
            print("cleaned local repo directory")


if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True  # only for testing
    with socketserver.TCPServer(("", PORT), BuildRequestHandler) as MainServer:
        print("serving at port", PORT)
        MainServer.serve_forever()