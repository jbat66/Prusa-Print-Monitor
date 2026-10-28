# Changelog

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
