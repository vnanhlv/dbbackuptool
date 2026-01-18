# Database Backup & Restore Tool

A Python-based utility to automate the process of migrating a PostgreSQL database from a Production Docker container to a Staging Docker container. It supports a full automated pipeline or individual step-by-step execution.

## Features
- **Backup Production**: Dumps the database from the Production Docker container.
- **Download**: Transfers the backup file from Production to your Local machine.
- **Upload**: Transfers the backup file from Local to the Staging server.
- **Restore Staging**: Restores the database on the Staging Docker container (with optional schema cleanup).
- **Staging Backup**: Supports backing up the existing Staging database before replacement.
- **Safety**: Timestamped filenames prevent overwrites.
- **Clean Restore**: disconnects active users and resets schema to avoid conflicts.
- **Restore Local**: Restore a backup directly to your local PostgreSQL database (Windows/Non-Docker supported).

## Prerequisites
1. **Python 3.6+**
2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```
3. **SSH Access**: You must have SSH keys configured for both Production and Staging servers.

## Configuration
Rename `config.yaml.example` to  `config.yaml` and edit with your server details:
- **Keys**: Use `/` for paths (e.g., `D:/path/to/key`).
- **Passphrase**: Add `ssh_passphrase: "your_pass"` if your SSH key has a password.
- **Database**: Ensure `db_user`, `db_name`, and `db_password` are correct.

## Quick Start (Full Pipeline)
To backup Production, download, upload, and restore to Staging in one go:
```powershell
# Warning: This updates Staging immediately
python backup_restore.py full
```

## Common Workflows

### 1. Safe Deployment (Backup Staging First)
If you want to play it safe, backup your current Staging DB before overwriting it with Production data.

1. **Backup current Staging DB**:
   ```powershell
   python backup_restore.py backup_staging
   # Output: staging_prod_chatbot_backup_20260118_090000.sql.gz
   ```
2. **Download it (optional)**:
   ```powershell
   python backup_restore.py download_staging
   ```
3. **Overwrite Staging with Production Data**:
   ```powershell
   # Use --clean to drop old schema/tables first (Recommended)
   python backup_restore.py full --clean
   ```

### 2. Manual Step-by-Step
If you want to control each step or resume from a failed step.

**Step 1: Backup Prod**
```powershell
python backup_restore.py backup
# Creates a timestamped file on Prod, e.g., prod_backup_2026...sql.gz
```

**Step 2: Download**
```powershell
# Auto-detects the latest file on Prod
python backup_restore.py download
```

**Step 3: Upload**
```powershell
# Auto-detects the latest file on Local
python backup_restore.py upload
```

**Step 4: Restore**
```powershell
# Restores the latest uploaded file to Staging
# --clean ensures clean state by dropping schema 'public'
python backup_restore.py restore --clean
```

### 3. Working with Specific Files
If you have multiple backups and want to use a specific one:
```powershell
# Upload a specific old backup
python backup_restore.py upload --file old_backup_2025.sql.gz

# Restore that specific file
python backup_restore.py restore --file old_backup_2025.sql.gz --clean
```


### 4. Restore to Local Machine (No Docker)
If you want to pull data from Production to your local development machine (Windows).
Ensure you have `psql` installed and `config.yaml` configured with local DB credentials.

```powershell
# 1. Backup Prod
python backup_restore.py backup

# 2. Download to Local
python backup_restore.py download

# 3. Restore to Local DB
# Use --clean to reset local schema 'public' before restoring
python backup_restore.py restore_local --clean
```

## Command Reference

| Action | Description | Options |
|--------|-------------|---------|
| `full` | Run all steps: Backup Prod -> DL -> UL -> Restore Staging | `--clean` |
| `backup` | Dump Prod DB to file on Prod server | |
| `download`| SCP latest backup from Prod to Local | `--file` |
| `upload` | SCP latest backup from Local to Staging | `--file` |
| `restore` | Restore DB on Staging | `--file`, `--clean` |
| `restore_local`| Restore DB on Local Machine (Non-Docker) | `--file`, `--clean` |
| `backup_staging` | Dump Staging DB to file on Staging server | |
| `download_staging`| SCP latest backup from Staging to Local | `--file` |
| `test` | Test SSH and DB connections to both servers | |

## Troubleshooting
- **Authentication failed**: Check `ssh_key_path` and `ssh_passphrase` in `config.yaml`.
- **"Already exists" errors during restore**: Use `--clean` flag to start fresh.
- **Hang/Timeout**: Check network speed or double-check `db_password` is correct (pg_dump might be waiting for input).