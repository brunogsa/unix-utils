#!/usr/bin/env python3
"""Upload a .docx to Google Drive, converting to a native Google Doc.

Reads the file from disk (no inline base64), using a gcloud-minted Drive token.
This is the scalable upload mechanism the future skill will encode.

Usage:
  gdoc_upload.py test  <docx>                 -> create a NEW scratch Doc, print id
  gdoc_upload.py update <fileId> <docx>        -> replace EXISTING Doc content in place
  gdoc_upload.py export <fileId> <out.html>    -> export Doc back to HTML (verification)
  gdoc_upload.py delete <fileId>               -> trash a Doc (scratch cleanup)
"""
import json
import subprocess
import sys
import urllib.request
import uuid

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
GDOC_MIME = "application/vnd.google-apps.document"


def token():
    r = subprocess.run(
        ["gcloud", "auth", "print-access-token", f"--scopes={DRIVE_SCOPE}"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.exit(f"TOKEN ERROR (re-auth needed: gcloud auth login --enable-gdrive-access):\n{r.stderr}")
    return r.stdout.strip()


def multipart_upload(method, url, metadata, docx_path):
    boundary = "===" + uuid.uuid4().hex + "==="
    with open(docx_path, "rb") as f:
        media = f.read()
    pre = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {DOCX_MIME}\r\n\r\n"
    ).encode("utf-8")
    post = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = pre + media + post
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token()}")
    req.add_header("Content-Type", f"multipart/related; boundary={boundary}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_test(docx):
    meta = {"name": "_hld_conv_scratch", "mimeType": GDOC_MIME}
    url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,mimeType"
    out = multipart_upload("POST", url, meta, docx)
    print(json.dumps(out))


def cmd_update(file_id, docx):
    meta = {"mimeType": GDOC_MIME}
    url = f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=multipart&fields=id,name,mimeType,modifiedTime"
    out = multipart_upload("PATCH", url, meta, docx)
    print(json.dumps(out))


def cmd_export(file_id, out_path):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType=text/html"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token()}")
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"exported {len(data)} bytes -> {out_path}")


def cmd_delete(file_id):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Authorization", f"Bearer {token()}")
    urllib.request.urlopen(req)
    print(f"deleted {file_id}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    {"test": lambda: cmd_test(a[1]),
     "update": lambda: cmd_update(a[1], a[2]),
     "export": lambda: cmd_export(a[1], a[2]),
     "delete": lambda: cmd_delete(a[1])}[a[0]]()
