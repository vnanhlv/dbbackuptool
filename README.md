# Server Utilities

Unless specified otherwise, all tools require Python 3.6+ and dependencies listed in `requirements.txt`.

## Available Tools

### 1. [BackupTool](backuptool/README.md)
Located in `backuptool/`.
Automates PostgreSQL database backup and restore operations between Production, Staging, and Local environments.
- **Key Features**: Backup Prod, Restore Staging, Data Sync.
- **Run**: `python backuptool/backup_restore.py --help`

### 2. [LogTool](logtool/README.md)
Located in `logtool/`.
Downloads rotated log files from remote servers to free up space and analyze locally.
- **Key Features**: Auto-download `*.1.log`, `*.2.log`, delete from server after download.
- **Run**: `python logtool/log_downloader.py --help`

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure each tool by creating `config.yaml` in their respective directories (`backuptool/config.yaml`, `logtool/config.yaml`).
