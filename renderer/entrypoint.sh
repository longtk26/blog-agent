#!/bin/sh
# One shared virtual display for every draw.io export (starting xvfb-run per render costs ~1 s each time).
set -e
Xvfb "${DISPLAY:-:99}" -screen 0 1920x1080x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
exec node /app/server.js
