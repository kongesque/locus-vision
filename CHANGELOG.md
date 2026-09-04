# Changelog

All notable changes to Locus Vision are documented here.

## [0.1.0-beta.1] - 2026-09-04

First public beta.

### Highlights

- Real-time camera monitoring with object detection, tracking, zones, lines, heatmaps, and event feeds.
- Batch video analytics with a persistent queue, progress reporting, result playback, and JSON export.
- Dashboard, system telemetry, historical analytics, model management, and first-run administration.
- Docker-based self-hosting for edge devices, including Raspberry Pi and Hailo-8L detection.

### Release hardening

- Require authentication for camera, video, analytics, system, livestream, and model APIs.
- Restore CSRF checks, restrict credentialed CORS, use protocol-aware secure cookies, and make refresh-token revocation effective.
- Generate and persist a unique JWT signing secret when an operator does not provide one.
- Replace the Python 3.12-incompatible TFLite dependency with Google LiteRT.
- Package COCO class labels in clean checkouts and pin the Docker pnpm toolchain.
- Add frontend/backend CI and authentication security regression tests.

[0.1.0-beta.1]: https://github.com/kongesque/locus-vision/releases/tag/v0.1.0-beta.1
