#!/bin/sh
# `make dev` guard: local dev runs over plain http, where a Secure session cookie is dropped by the
# browser (login would loop). A .env that is still an untouched copy of .env.example gets
# COOKIE_SECURE=false; any other .env must already say so. Production defaults stay untouched.
set -eu
file=${ENV_FILE:-.env}
example=${ENV_EXAMPLE:-.env.example}
if grep -q '^COOKIE_SECURE=false' "$file"; then
    exit 0
fi
if cmp -s "$file" "$example"; then
    "$(dirname "$0")/set-env.sh" COOKIE_SECURE false
    echo "make dev: $file was a fresh copy of $example; set COOKIE_SECURE=false for http://localhost."
    exit 0
fi
echo "make dev: set COOKIE_SECURE=false in $file (local dev is plain http; the browser drops a Secure cookie)." >&2
exit 1
