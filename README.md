<p align="center"><img src="assets/icon.png" alt="Prusa Print Monitor" width="320"></p>

# Prusa Print Monitor — version 0.2.11

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
| `SOUND_FILE` | `/mnt/user/appdata/prusa-print-monitor/sounds/AlarmSoundEffect.mp3` | Select the MP3 inside Sounds Folder; the filename is resolved under `/sounds`. |
| `TZ` | `America/Denver` | Container timezone; UI times use the browser timezone. |

All intervals must be positive integers. The server listens on container port 8085. It exits with a configuration error if alerts are enabled without a readable sound file.

### Get the PrusaLink API key from Prusa Connect

1. Sign in at [Prusa Connect](https://connect.prusa3d.com/) and select your printer.
2. Open that printer's **Settings** tab and find the **API keys / PrusaLink** section.
3. Copy the **PrusaLink API key** (the local printer credential), rather than the separate Prusa Connect cloud API key. Paste it into this container's `API_KEY`; put the displayed printer IP into `PRINTER_URL`.
4. If no local credential is shown, enable PrusaLink on the printer. On supported MK4/XL-style firmware, open **Settings → Network → PrusaLink** on the printer: its password is the local PrusaLink API key, and the default username is `maker`. Generate/reset the local password using the controls offered by your printer/firmware when needed, then copy the new value. Some PrusaLink versions expose credentials through their local web setup instead.

Prusa Connect's Settings tab displays the local credential; generating a separate cloud API key does not create a replacement local PrusaLink password. This dashboard uses HTTP Digest authentication: for older Raspberry Pi PrusaLink installations, use their configured local username/password.

Sources: [Prusa's credentials instructions](https://help.prusa3d.com/wp-content/uploads/generated/prusa-connect-prusalink_1636_guide_222961_en_2026-05-13.pdf), [PrusaLink troubleshooting](https://help.prusa3d.com/article/prusalink-troubleshooting_304411).

### Sounds

Set **Sounds Folder** to the writable host directory where you want the sound files saved. Default: `/mnt/user/appdata/prusa-print-monitor/sounds`, mounted at container `/sounds`. Each time the container starts, it copies missing bundled files into that directory:

- `AlarmSoundEffect.mp3` (default)
- `ClockChimes.mp3`
- `Cuckoo.mp3`
- `RedAlert.mp3`

Existing files are preserved. The startup helper seeds the directory before dropping to user `monitor` (UID 10001) and starting the dashboard. The four original MP3s are packaged at `/app/assets/sounds` so the host volume does not hide them.

**Sound File** defaults to `/mnt/user/appdata/prusa-print-monitor/sounds/AlarmSoundEffect.mp3`. Select another bundled sound by changing the filename (case-sensitive), or add your own MP3 to Sounds Folder. This entry is the `SOUND_FILE` variable, not a separate file mount: only its filename is resolved inside `/sounds`. When moving the host folder, update **Sounds Folder** and the path displayed in **Sound File**. There is no `ALERT_SOUND_FILE` variable.

Set `ALERT=true` and click **Enable sounds** in each browser. MP3 plays directly on the viewing device without conversion; the NAS needs no sound hardware. The host directory must allow the startup helper to create missing files, and UID 10001 must be able to read them. Files on a network share with root-squash may require host-side permission changes.

To upgrade from 0.2.8 or earlier, remove the old single-file `/sounds` mount and replace it with the new writable **Sounds Folder** directory mount. Add **Sound File** as the selector variable with your selected filename. An older single-file mount can still play its existing audio, but it cannot receive all four bundled files.

The first successful status is the baseline and does not alert. Every subsequent observed printer state change creates an alert, including changes to PRINTING and IDLE. It repeats at `ALERT_REPEAT_SECONDS` until **Acknowledge**. **Mute** temporarily suppresses sound without acknowledging; unmuting resumes pending alerts. A newer state change requires a new acknowledgment. Each viewing browser manages its own audio and acknowledgment. Reloading establishes a new baseline. Connection failures do not create printer-state alerts. Changes while no browser is open do not sound later. Browsers need an initial user gesture for audio and may suspend background tabs; use an awake foreground display for dependable alerts.

### Camera

Set `CAMERA=true` and configure `CAMERA_URL`, for example `rtsp://user:password@192.168.1.20:554/live`. Click **Enable Camera** to turn the feed on; click **Camera Enabled** to stop it. The setting allows camera access; feeds start only on request. FFmpeg converts RTSP or HTTP video streams to MJPEG at 3 fps and 960px width. Each viewer consumes one conversion process, limited to four concurrent viewers. Camera URLs and passwords stay on the server. A feed failure shows a message; toggle off/on to reconnect. The server must be able to reach the camera and printer on your LAN.

### Display behavior

The browser checks the dashboard every two seconds; the backend polls the printer every `REFRESH_SECONDS`. Countdown values update every second between polls while PRINTING. PAUSED freezes countdowns and hides the estimated finish. Connection failures retain clearly marked last-known data and freeze countdowns. Missing/invalid times show a dash; a missing or zero filament-change value means no scheduled change is reported. An elapsed filament countdown shows “Change due” until the printer provides an update. Printer state labels are shown as reported, including UNKNOWN or firmware-specific values. Layout choice is saved per browser; narrow screens also adapt automatically.

This is a trusted-LAN dashboard with no user login. Anyone with access to its web port can view printer status, the configured alert audio, and the enabled camera. Do not expose it directly to the internet. Printer credentials are stored in container environment settings, visible to UNRAID administrators.

## Build or run yourself

```sh
git clone https://github.com/jbat66/Prusa-Print-Monitor.git
cd Prusa-Print-Monitor
cp .env.example .env
# Edit .env with your own printer settings.
# Edit the Compose Sounds Folder bind source if using a different host folder.
docker compose up -d --build
```

For plain Docker, build with `docker build -t prusa-print-monitor .`, then:

```sh
docker run -d --name prusa-print-monitor --restart unless-stopped \
  -p 8085:8085 --env-file .env \
  -v /mnt/user/appdata/prusa-print-monitor/sounds:/sounds:rw \
  prusa-print-monitor
```

To run without Docker, Python 3.13 requires no third-party packages: set the environment variables, then run `python app.py`. Install FFmpeg separately if camera support is enabled. For alerts without Docker, create the `/sounds` directory, copy in the MP3s, and set `SOUND_FILE` to your chosen filename. `/health` checks the web service, not the printer; `/api/status` reports printer connectivity separately.

## Development checks

```sh
python -m unittest discover -s tests -v
node --test tests/dashboard.test.cjs
```

Tests cover state transitions, repeat/acknowledge/mute behavior, disconnections, invalid payloads, web routes, camera controls, credential isolation, and template variable order. CI builds Linux AMD64 and ARM64 images. To update an UNRAID installation after a new image is published, use **Check for Updates** on its Docker page.


## Updating to version 0.2.11

Images are published as `ghcr.io/jbat66/prusa-print-monitor:0.2.11` and `:latest`. The source release is tagged `v0.2.11`; `VERSION` is the application version, also shown in the dashboard header and status API. See [CHANGELOG.md](CHANGELOG.md).

Existing UNRAID containers retain their old settings. Update the container configuration using the new template: change the container port to **8085** (and host port to 8085 unless you prefer another port), remove `ALERT_SOUND_FILE`, replace the old single-file mount with a writable **Sounds Folder** directory at `/sounds`, and set **Sound File** to `/mnt/user/appdata/prusa-print-monitor/sounds/AlarmSoundEffect.mp3`, and set `ALERT_REPEAT_SECONDS=60`. The camera URL is now unmasked. Update the image and recreate/apply the container.

The existing notice row reports whether alerts, camera, or both are disabled, without adding another row. When both features are enabled, audio readiness or pending alerts use that same notice.


### Container stop troubleshooting

Version 0.2.2 handles Docker SIGTERM and stops camera workers cleanly. Update to `:0.2.2` or the current `:latest`. If an older container refuses to stop, use the UNRAID terminal to run `docker stop --time 5 Prusa-Print-Monitor` (substitute the exact container name). Docker will force-stop it after the timeout if necessary. If it still runs, try `docker kill Prusa-Print-Monitor` once and save any error text; a failure to force-stop needs Docker/host diagnostics. Then apply the updated image.


### Camera diagnostics (0.2.3)

Open the container's **Logs** screen in UNRAID, then click **Enable Camera** in the dashboard. Timestamped entries named `Prusa-Print-Monitor.log` report connection attempts, FFmpeg errors, first video frames, stream endings and timeouts. These entries go to container stdout, which Docker/UNRAID captures; no separate host log-file mapping is required. Printer connection/state changes and shutdown also appear there. Camera URL credentials and the printer API key are redacted.

The dashboard checks the camera session status every two seconds and reports a failure if no complete frame arrives for 15 seconds. Check the log for authentication errors, connection refused, unsupported streams or timeouts. Confirm CAMERA_URL is a camera video stream reachable from UNRAID; for RTSP, use the camera's documented stream path. Click **Camera Enabled** to stop, then **Enable Camera** to retry.


Version 0.2.4 fixes the RTSP startup error `Option rw_timeout not found`. RTSP cameras use the demuxer-specific `timeout` option; HTTP/HTTPS streams retain `rw_timeout`. No CAMERA_URL change is required for this fix.


Version 0.2.5 positions the enabled camera beside Printer Status on wide screens in Desktop (up to 360px wide) and Across the Room (up to 640px wide). Compact Corner and Mobile keep the camera below the status/metrics, and narrow screens stack the content. Changing layouts preserves the running camera stream.


Version 0.2.6 alphabetizes the layout menu and shows Acknowledge beside Layout only while a state-change alert is pending. Mobile devices start in Mobile layout on each page load, even if another layout was saved; you can still choose another layout during the session. Full screen is hidden on mobile devices. Desktop browsers retain their saved layout and Full screen control.


Version 0.2.7 places Acknowledge in its own conditional row above Layout. Mute appears only after Enable sounds succeeds. Muting changes the notice to “Sounds muted • Unmute to allow alerts to play”. A simplified favicon is served at `/favicon.ico` with 16, 24, 32, 48, 64, 128 and 256 pixel entries.


Version 0.2.8 colors the ready-sounds notice green and keeps muted/disabled notices orange. The simplified `assets/app-icon.png` is used in the web header and UNRAID template; the original large `assets/icon.png` is retained as the README illustration. Existing UNRAID installations should update the Icon URL to `https://raw.githubusercontent.com/jbat66/Prusa-Print-Monitor/main/assets/app-icon.png`.


Version 0.2.10 adds a live clock using the viewing device’s local time. Enable sounds silently unlocks Web Audio instead of playing the alarm as a test. Each actual state-change alert uses a fresh playback source, allowing repeat playback until acknowledged. If iOS suspends audio, the dashboard asks you to tap Enable sounds again. Keep the page foreground and the phone awake for dependable alerts; browser/phone background suspension still applies. Audio is decoded once per page session, so refresh after changing the selected sound.


Version 0.2.11 adds camera focus mode: double-click or double-tap the live camera to expand it to the selected layout’s normal full width. The existing header/clock/connection indicator, sound notice, Acknowledge row and footer remain; printer status and timing panels are hidden. Double-click again, press Escape or choose Back to status to return. Layout changes continue to work without restarting the camera. Enable sounds disappears after success and returns if audio permission needs to be restored.
