# LogTool

A utility to download and manage rotated log files from remote servers.

## Features
- **Download Rotated Logs**: Targeted download of `*.1.log`, `*.2.log` files.
- **Auto-Cleanup**: Can automatically delete files from the remote server after successful download (configurable).
- **Pattern Matching**: Flexible file matching patterns.

## Configuration
Copy `config.yaml.example` to `config.yaml` and configure:
```yaml
server:
  host: "your_server_ip"
  user: "your_username"
  ssh_key_path: "/path/to/key"

logs:
  remote_path: "/path/to/logs"
  local_path: "logs"
  import_patterns: ["*.1.log", "*.2.log"]

settings:
  after_download: "delete" # or "keep"
```

## Usage
Run the downloader:
```bash
python log_downloader.py
```
