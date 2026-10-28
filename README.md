# Prusa Print Monitor

A Docker dashboard for a PrusaLink printer, designed for UNRAID, phones, a desktop corner or a room display. Uses the same HTTP Digest authentication and status fields as `printer-state-display.sh`. No printer credentials are sent to the browser.

- Large color-coded printer state, remaining time and estimated finish.
- Separate filament-change countdown, connection health and last successful update.
- Desktop, compact, mobile and across-the-room layouts selectable in the web UI.
- State-change sounds with mute, acknowledge and full-screen controls.
- Optional RTSP/HTTP camera converted to browser-viewable MJPEG by FFmpeg.

## Install on UNRAID

The GitHub Actions workflow publishes `ghcr.io/jbat66/prusa-print-monitor:latest` after tests pass on `main`. The first image must finish publishing before installing. The GHCR package must be public for UNRAID to pull without registry credentials (GitHub repository → Packages → prusa-print-monitor → Package settings → Change visibility → Public, if needed).

1. Download [`unraid/prusa-print-monitor.xml`](unraid/prusa-print-monitor.xml). Save it on your UNRAID server at `/boot/config/plugins/dockerMan/templates-user/my-prusa-print-monitor.xml`.
2. In UNRAID, open **Docker → Add Container**, and select **Prusa-Print-Monitor** from the template list.
3. Replace `X.X.X.X` in `PRINTER_URL` with your printer address and replace `PUT-KEY-HERE` with your PrusaLink password/API key. Default username is `maker`.
4. Set a free host web port (default `8080`), apply, and use the container's **WebUI** menu. Open `http://YOUR-UNRAID-IP:8080` from other devices.

Every template setting is visible in basic view. The first eight variables appear in the requested order:

| Variable | Default | Instructions |
| --- | --- | --- |
| `PRINTER_URL` | `http://X.X.X.X/api/v1/status` | Replace the example IP with your printer IP. |
| `API_USER` | `maker` | PrusaLink Digest username. |
| `API_KEY` | `PUT-KEY-HERE` | Replace with your printer key/password. |
| `REFRESH_SECONDS` | `60` | Printer polling interval in seconds. |
| `ALERT_SOUND_FILE` | `/sounds/alert.mp3` | Container path to your MP3/WAV file. |
| `ALERT` | `false` | If true, supply the file via `ALERT_SOUND_FILE`. |
| `CAMERA` | `false` | If true, replace `CAMERA_URL` with a working stream URL. |
| `CAMERA_URL` | `rtsp://x.x.x.x/live` | Replace with your actual RTSP/HTTP stream. |
| `ALERT_REPEAT_SECONDS` | `30` | Repeat interval until acknowledged. |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Printer request timeout. |
| `TZ` | `America/Denver` | Container timezone; UI times use the browser timezone. |

All intervals must be positive integers. The server listens on container port 8080. It exits with a configuration error if alerts are enabled without a readable sound file.

### Sounds

Create `/mnt/user/appdata/prusa-print-monitor/sounds` on UNRAID and put your own `alert.mp3` inside. The template maps that folder read-only to `/sounds`. `ALERT_SOUND_FILE` is the **container** path, not the UNRAID host path. Ensure UID 10001 can read the folder/file, set `ALERT=true`, then click **Enable sounds** in each browser. Audio plays on the viewing device, so the NAS needs no sound hardware. Use a short MP3 or WAV supported by the browser.

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
docker compose up -d --build
```

For plain Docker, build with `docker build -t prusa-print-monitor .`, then:

```sh
docker run -d --name prusa-print-monitor --restart unless-stopped \
  -p 8080:8080 --env-file .env \
  -v /mnt/user/appdata/prusa-print-monitor/sounds:/sounds:ro \
  prusa-print-monitor
```

To run without Docker, Python 3.13 requires no third-party packages: set the environment variables, then run `python app.py`. Install FFmpeg separately if camera support is enabled. `/health` checks the web service, not the printer; `/api/status` reports printer connectivity separately.

## Development checks

```sh
python -m unittest discover -s tests -v
node --test tests/dashboard.test.cjs
```

Tests cover state transitions, repeat/acknowledge/mute behavior, disconnections, invalid payloads, web routes, camera controls, credential isolation, and template variable order. CI builds Linux AMD64 and ARM64 images. To update an UNRAID installation after a new image is published, use **Check for Updates** on its Docker page.
