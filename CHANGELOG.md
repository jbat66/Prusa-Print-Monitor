# Changelog

## 0.2.7

- Place the conditional Acknowledge button in its own row above the Layout controls.
- Show Mute only after browser sounds have been enabled; show the muted/unmute status immediately.
- Add a simplified printer logo and a multi-resolution favicon.ico served locally for browser tabs.

## 0.2.6

- Alphabetize layouts: Across the Room, Compact Corner, Desktop, Mobile.
- Place Acknowledge beside Layout and show it only for a pending state-change alert.
- Automatically start phones and tablets in Mobile layout, including iPads using desktop-style identification.
- Hide Full screen on mobile devices while keeping manual layout selection available.

## 0.2.5

- Place the camera to the right of Printer Status in Desktop and Across the Room layouts on wide screens.
- Use a smaller Desktop preview (up to 360px wide) and a larger Across the Room preview (up to 640px wide).
- Preserve the existing Compact Corner and Mobile camera placement. Narrow screens continue to stack the feed.
- Change layout through CSS without restarting the camera stream.

## 0.2.4

- Fix RTSP camera startup by using the RTSP timeout option without the incompatible rw_timeout option. Retain rw_timeout for HTTP/HTTPS cameras.
- Wait for FFmpeg's exit status before logging a stream failure.
- Check the actual container FFmpeg RTSP option parser during image smoke tests.

## 0.2.3

- Log camera requests, FFmpeg errors, first video frames, stream endings and timeouts to the UNRAID container log with credentials redacted.
- Report camera status to the dashboard and stop streams that produce no complete frames for 15 seconds.
- Use explicit RTSP timeouts and single-threaded MJPEG encoding.
- Rename camera controls to Enable Camera / Camera Enabled.
- Add the application icon beside the dashboard name.

## 0.2.2

- Handle SIGTERM and SIGINT explicitly so Docker/UNRAID can stop the Python container cleanly.
- Wake polling waits on shutdown and stop active FFmpeg camera processes with bounded waits.
- Verify clean signal shutdown and Docker exit code 0 in regression and container tests.

## 0.2.1

- Correct the Sound File example to redalert.mp3 in the UNRAID template, Compose and documentation.
- Serve the mounted MP3 directly as audio/mpeg without audio conversion or caching.

## 0.2

- Use container port 8085 throughout the application, Docker health check, Compose, UNRAID template and documentation.
- Default alert repeats to 60 seconds.
- Show the camera stream URL without masking in the UNRAID template.
- Replace ALERT_SOUND_FILE and the Sounds directory mount with a Sound File host-file mount at the fixed container path /sounds.
- Configure alert audio through a single Sound File mount.
- Report disabled alerts/camera together in the existing dashboard notice row.
- Add an application version, dashboard version indicator, source tag and versioned Docker image.

## Before versioning

- Initial dashboard, Docker publishing, UNRAID template and application icon.
