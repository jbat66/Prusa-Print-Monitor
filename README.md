# Prusa Print Monitor — version 0.2.2

A Docker dashboard for a PrusaLink printer, designed for UNRAID, phones, a desktop corner or a room display. Uses the same HTTP Digest authentication and status fields as `printer-state-display.sh`. No printer credentials are sent to the browser.

- Large color-coded printer state, remaining time and estimated finish.
- Separate filament-change countdown, connection health and last successful update.
- Desktop, compact, mobile and across-the-room layouts selectable in the web UI.
- State-change sounds with mute, acknowledge and full-screen controls.
- Optional RTSP/HTTP camera converted to browser-viewable MJPEG by FFmpeg.

## Install on UNRAID

1. Download [`unraid/prusa-print-monitor.xml`](unraid/prusa-print-monitor.xml). Save it on your UNRAID server at `/boot/config/plugins/dockerMan/templates-user/my-prusa-print-monitor.xml`.
2. In UNRAID, open **Docker → Add Container**, and select **Prusa-Print-Monitor** from the template list.
3. Replace `X.X.X.X` in `PRINTER_URL` with your printer address and replace `PUT-KEY-HERE` with your PrusaLink password/API key. Default username is `maker`.
4. Set a free host web port (default `8085`), apply, and use the container's **WebUI** menu. Open `http://YOUR-UNRAID-IP:8085` from other devices.

Every template setting is visible in basic view. The printer and feature variables appear in the requested order:

| Variable | Default | Instructions |
| --- | --- | --- |
| `PRINTER_URL` | `http://X.X.X.X/api/v1/status` | Replace the example IP with your printer IP. |
| `API_USER` | `maker` | PrusaLink Digest username. |
| `API_KEY` | `PUT-KEY-HERE` | Replace with your printer key/password. |
| `REFRESH_SECONDS` | `60` | Printer polling interval in seconds. |
| `ALERT` | `false` | If true, select your host audio file using **Sound File**. |
| `CAMERA` | `false` | If true, replace `CAMERA_URL` with a working stream URL. |
| `CAMERA_URL` | `rtsp://x.x.x.x/live` | Replace with your actual RTSP/HTTP stream. |
| `ALERT_REPEAT_SECONDS` | `60` | Repeat interval until acknowledged. |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Printer request timeout. |
| `TZ` | `America/Denver` | Container timezone; UI times use the browser timezone. |

All intervals must be positive integers. The server listens on container port 8085. It exits with a configuration error if alerts are enabled without a readable sound file.

### Sounds

Set **Sound File** to the full path of an existing host audio file, for example `/mnt/user/appdata/prusa-print-monitor/sounds/redalert.mp3`. The template mounts that single file read-only at the fixed container path `/sounds`. There is no `ALERT_SOUND_FILE` environment variable. Ensure UID 10001 can read the file, set `ALERT=true`, then click **Enable sounds** in each browser. The MP3 file is served directly to the browser without conversion or audio caching. Audio plays on the viewing device, so the NAS needs no sound hardware.

The first successful status is the baseline and does not alert. Every subsequent observed printer state change creates an alert, including changes to PRINTING and IDLE. It repeats at `ALERT_REPEAT_SECONDS` until **Acknowledge**. **Mute** temporarily suppresses sound without acknowledging; unmuting resumes pending alerts. A newer state change requires a new acknowledgment. Each viewing browser manages its own audio and acknowledgment. Reloading establishes a new baseline. Connection failures do not create printer-state alerts. Changes while no browser is open do not sound later. Browsers need an initial user gesture for audio and may suspend background tabs; use an awake foreground display for dependable alerts.

### Camera

Set `CAMERA=true` and configure `CAMERA_URL`, for example `rtsp://user:password@192.168.1.20:554/live`. Click **Camera off** to turn the feed on; click again to stop it. The setting allows camera access; feeds start only on request. FFmpeg converts RTSP or HTTP video streams to MJPEG at 3 fps and 960px width. Each viewer consumes one conversion process, limited to four concurrent viewers. Camera URLs and passwords stay on the server. A feed failure shows a message; toggle off/on to reconnect. The server must be able to reach the camera and printer on your LAN.

### Display behavior

The browser checks the dashboard every two seconds; the backend polls the printer every `REFRESH_SECONDS`. Countdown values update every second between polls while PRINTING. PAUSED freezes countdowns and hides the estimated finish. Connection failures retain clearly marked last-known data and freeze countdowns. Missing/invalid times show a dash; a missing or zero filament-change value means no scheduled change is reported. An elapsed filament countdown shows “Change due” until the printer provides an update. Printer state labels are shown as reported, including UNKNOWN or firmware-specific values. Layout choice is saved per browser; narrow screens also adapt automatically.

This is a trusted-LAN dashboard with no user login. Anyone with access to its web port can view printer status, the configured alert audio, and the enabled camera. Do not expose it directly to the internet. Printer credentials are stored in container environment settings, visible to UNRAID administrators.

## Build or run yourself

```sh
git clone https://github.com/jbat66/Prusa-Print-Monitor.git
cd Prusa-Print-Monitor
cp .env.example .env
# Edit .env with your own printer settings.
# Edit the compose bind source to an existing host sound file, or remove
# the volumes section when ALERT=false and you do not want to mount a file.
docker compose up -d --build
```

For plain Docker, build with `docker build -t prusa-print-monitor .`, then:

```sh
docker run -d --name prusa-print-monitor --restart unless-stopped \
  -p 8085:8085 --env-file .env \
  --mount type=bind,source=/mnt/user/appdata/prusa-print-monitor/sounds/redalert.mp3,target=/sounds,readonly \
  prusa-print-monitor
```

To run without Docker, Python 3.13 requires no third-party packages: set the environment variables, then run `python app.py`. Install FFmpeg separately if camera support is enabled. For alerts without Docker, place the audio file at `/sounds`. `/health` checks the web service, not the printer; `/api/status` reports printer connectivity separately.

## Development checks

```sh
python -m unittest discover -s tests -v
node --test tests/dashboard.test.cjs
```

Tests cover state transitions, repeat/acknowledge/mute behavior, disconnections, invalid payloads, web routes, camera controls, credential isolation, and template variable order. CI builds Linux AMD64 and ARM64 images. To update an UNRAID installation after a new image is published, use **Check for Updates** on its Docker page.


## Updating to version 0.2.2

Images are published as `ghcr.io/jbat66/prusa-print-monitor:0.2.2` and `:latest`. The source release is tagged `v0.2.2`; `VERSION` is the application version, also shown in the dashboard header and status API. See [CHANGELOG.md](CHANGELOG.md).

Existing UNRAID containers retain their old settings. Update the container configuration using the new template: change the container port to **8085** (and host port to 8085 unless you prefer another port), remove `ALERT_SOUND_FILE`, replace the old Sounds directory mount with **Sound File** pointing to an existing host file and container target `/sounds`, and set `ALERT_REPEAT_SECONDS=60`. The camera URL is now unmasked. Update the image and recreate/apply the container.

The existing notice row reports whether alerts, camera, or both are disabled, without adding another row. When both features are enabled, audio readiness or pending alerts use that same notice.


### Container stop troubleshooting

Version 0.2.2 handles Docker SIGTERM and stops camera workers cleanly. Update to `:0.2.2` or the current `:latest`. If an older container refuses to stop, use the UNRAID terminal to run `docker stop --time 5 Prusa-Print-Monitor` (substitute the exact container name). Docker will force-stop it after the timeout if necessary. If it still runs, try `docker kill Prusa-Print-Monitor` once and save any error text; a failure to force-stop needs Docker/host diagnostics. Then apply the updated image.
