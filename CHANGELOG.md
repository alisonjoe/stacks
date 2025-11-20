# Changelog

## [1.0.3]

### Features

- Refectored large parts of the downloader:
  - Added aria2 support for multi downloading
  - Added ability to use Flaresolverr
  - Updated the download logic to better catch download links

### Architecture

- Broke out everything into modules

## [1.0.2] - 2025-11-18

### Hotfix

- Fixed issue where slow downloads sometimes would return bin-files instead of the actual downloads

## [1.0.1] - 2025-11-18

### Hotfix

- Fixed issue where some scraped mirrors would be relative instead of absolute, making downloads fail

## [1.0.0] - 2025-11-19

- Initial stable release
