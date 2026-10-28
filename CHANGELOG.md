# Changelog

## 0.2

- Use container port 8085 throughout the application, Docker health check, Compose, UNRAID template and documentation.
- Default alert repeats to 60 seconds.
- Show the camera stream URL without masking in the UNRAID template.
- Replace ALERT_SOUND_FILE and the Sounds directory mount with a Sound File host-file mount at the fixed container path /sounds.
- Decode alert files with FFmpeg to browser-compatible WAV, including MP2 sources.
- Report disabled alerts/camera together in the existing dashboard notice row.
- Add an application version, dashboard version indicator, source tag and versioned Docker image.

## Before versioning

- Initial dashboard, Docker publishing, UNRAID template and application icon.
