# Gitlab LaTeX Webhook

Python server that listens to gitlab webhooks and compiles latex files
specified in query params. Compiled pdfs are then uploaded to owncloud.

> **Note:** Relies on bash scripts `cloud_mkdir.sh` and `cloud_upload.sh`
> for the owncloud functionality and so, only works on linux.
> However, these can be replaced by scripts which handle the same
> functionality for other cloud services or other OSes.


## Requirements

* `Python 3.6+`
* `git`
* `pdflatex` (or some other latex compiler)
* `bibtex`


## Setup

1. Fix a machine that runs `server.py`. This machine is referred to
   as 'the server'.

2. Determine the IP/URL of the server and the port id (default: 3838).

3. Add a webhook to the gitlab repo which contains latex source with
   the following settings:
    
    ```text
    URL: <your-server-IP>:<port>?files=<your-file.tex>,<another.tex>
    Secret Token: <your-token>  # or leave it blank if you're feeling generous
    Trigger: Check "Push events"
    ```
   
4. Set the environment variable `GITLAB_SECRET_TOKEN` required by `server.py`
   (ignore if unset).

5. Set the environment variables `OWNCLOUD_URL`, `OWNCLOUD_USERNAME` and 
   `OWNCLOUD_PASSWORD` required by the owncloud bash scripts (see the section
   on Owncloud for details on how to find these).
   
6. Create a directory in owncloud for the compiled pdfs to go into and
   set the variable `build_dir` in both the bash scripts accordingly
   (default: `latex-builds`).


## Running

1. Start your server with `python3 server.py`

2. (Optional) Test your server using [these instructions][1].

> **Note:** Since webhooks only have about 10 seconds to provide their 
> response, the server sends back an intermediate response with the status
> so far in case the compiling takes much longer to run.

## Owncloud

1. The `OWNCLOUD_URL` can be obtained by clicking the `Settings` option
   in the bottom left and copying the URL from the `WebDAV` field without the 
   trailing slash.

2. The `OWNCLOUD_USERNAME` is the username you use to access owncloud.

3. For security reasons it is recommended to set an app-specific password by
   going to Account Settings &rarr; Security. Then use this password
   as the `OWNCLOUD_PASSWORD` environment variable.

[1]: https://gitlab.com/help/user/project/integrations/webhooks#testing-webhooks