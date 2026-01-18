import argparse
import yaml
import os
import sys
import datetime
from fabric import Connection
from invoke import UnexpectedExit

def load_config(config_path='config.yaml'):
    if not os.path.exists(config_path):
        print(f"Error: Config file '{config_path}' not found.")
        sys.exit(1)
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_connection(server_config):
    connect_kwargs = {
        "key_filename": server_config['ssh_key_path'],
    }
    
    if 'ssh_passphrase' in server_config:
        connect_kwargs['passphrase'] = server_config['ssh_passphrase']

    return Connection(
        host=server_config['host'],
        user=server_config['user'],
        port=server_config.get('port', 22),
        connect_kwargs=connect_kwargs
    )

def get_timestamped_filename(base_filename):
    """Appends a timestamp to the filename before the extensions."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if '.' in base_filename:
        parts = base_filename.split('.', 1)
        return f"{parts[0]}_{timestamp}.{parts[1]}"
    else:
        return f"{base_filename}_{timestamp}"

def backup_prod(config, filename):
    print(f"--- [STEP 1] Backing up Production Database (File: {filename}) ---")
    prod_conf = config['production']
    conn = get_connection(prod_conf)
    
    remote_path = f"/tmp/{filename}"
    
    env_vars = ""
    if 'db_password' in prod_conf and prod_conf['db_password']:
        env_vars = f"-e PGPASSWORD='{prod_conf['db_password']}' "
    
    dump_cmd = (
        f"docker exec {env_vars}{prod_conf['docker_container']} "
        f"pg_dump -U {prod_conf['db_user']} {prod_conf['db_name']} "
        f"| gzip > {remote_path}"
    )
    
    print(f"Executing: {dump_cmd}")
    try:
        conn.run(dump_cmd)
        print(f"Backup successful on remote: {remote_path}")
    except UnexpectedExit as e:
        print(f"Backup failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

def download_backup(config, filename):
    print(f"--- [STEP 2] Downloading Backup to Local (File: {filename}) ---")
    prod_conf = config['production']
    local_conf = config['local']
    
    if not os.path.exists(local_conf['backup_dir']):
        os.makedirs(local_conf['backup_dir'])
    
    local_path = os.path.join(local_conf['backup_dir'], filename)
    remote_path = f"/tmp/{filename}"
    
    conn = get_connection(prod_conf)
    
    print(f"Downloading {remote_path} to {local_path}...")
    try:
        conn.get(remote_path, local_path)
        print("Download successful.")
    except Exception as e:
        print(f"Download failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

def upload_progress(transferred, total):
    percent = (transferred / total) * 100
    sys.stdout.write(f"\rUploaded: {transferred} / {total} bytes ({percent:.1f}%)")
    sys.stdout.flush()

def upload_backup(config, filename):
    print(f"--- [STEP 3] Uploading Backup to Staging (File: {filename}) ---")
    staging_conf = config['staging']
    local_conf = config['local']
    
    local_path = os.path.join(local_conf['backup_dir'], filename)
    if not os.path.exists(local_path):
        print(f"Error: Local backup file not found at {local_path}")
        sys.exit(1)
    
    remote_path = f"/tmp/{filename}"
        
    conn = get_connection(staging_conf)
    
    print(f"Uploading {local_path} to {remote_path}...")
    try:
        sftp = conn.sftp()
        sftp.put(local_path, remote_path, callback=upload_progress)
        print("\nUpload successful.")
    except Exception as e:
        print(f"\nUpload failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

def backup_staging(config, filename):
    print(f"--- [STEP 0] Backing up Staging Database (File: {filename}) ---")
    staging_conf = config['staging']
    conn = get_connection(staging_conf)
    
    remote_path = f"/tmp/{filename}"
    
    env_vars = ""
    if 'db_password' in staging_conf and staging_conf['db_password']:
        env_vars = f"-e PGPASSWORD='{staging_conf['db_password']}' "
    
    dump_cmd = (
        f"docker exec {env_vars}{staging_conf['docker_container']} "
        f"pg_dump -U {staging_conf['db_user']} {staging_conf['db_name']} "
        f"| gzip > {remote_path}"
    )
    
    print(f"Executing: {dump_cmd}")
    try:
        conn.run(dump_cmd)
        print(f"Backup successful on staging remote: {remote_path}")
    except UnexpectedExit as e:
        print(f"Backup failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

def download_staging(config, filename):
    print(f"--- [STEP 0.5] Downloading Staging Backup to Local (File: {filename}) ---")
    staging_conf = config['staging']
    local_conf = config['local']
    
    if not os.path.exists(local_conf['backup_dir']):
        os.makedirs(local_conf['backup_dir'])
    
    local_path = os.path.join(local_conf['backup_dir'], filename)
    remote_path = f"/tmp/{filename}"
    
    conn = get_connection(staging_conf)
    
    print(f"Downloading {remote_path} to {local_path}...")
    try:
        conn.get(remote_path, local_path)
        print("Download successful.")
    except Exception as e:
        print(f"Download failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

def restore_staging(config, filename, clean=False):
    staging_conf = config['staging']
    conn = get_connection(staging_conf)
    remote_path = f"/tmp/{filename}"
    print(f"--- [STEP 4] Restoring Staging Database (File: {filename}) ---")
    
    env_vars = ""
    if 'db_password' in staging_conf and staging_conf['db_password']:
        env_vars = f"-e PGPASSWORD='{staging_conf['db_password']}' "
    
    # Clean DB if requested
    if clean:
        print("  [CLEAN] Dropping & Recreating 'public' schema to ensure a clean restore...")
        # 1. Terminate connections
        kill_cmd = (
            f"docker exec {env_vars}{staging_conf['docker_container']} "
            f"psql -U {staging_conf['db_user']} -d {staging_conf['db_name']} "
            f"-c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{staging_conf['db_name']}' AND pid <> pg_backend_pid();\""
        )
        # 2. Drop & Create Schema
        reset_schema_cmd = (
            f"docker exec {env_vars}{staging_conf['docker_container']} "
            f"psql -U {staging_conf['db_user']} -d {staging_conf['db_name']} "
            f"-c \"DROP SCHEMA public CASCADE; CREATE SCHEMA public;\""
        )
        
        try:
            conn.run(kill_cmd, hide=True, warn=True) # warn=True because it might fail if we kill ourself or no perms, but worth trying
            conn.run(reset_schema_cmd)
            print("  [CLEAN] Schema reset successful.")
        except Exception as e:
            print(f"  [CLEAN] Warning: Failed to reset schema: {e}")
            print("  Continuing with restore (might fail if conflicts exist)...")

    restore_cmd = (
        f"gunzip -c {remote_path} | "
        f"docker exec -i {env_vars}{staging_conf['docker_container']} "
        f"psql -U {staging_conf['db_user']} -d {staging_conf['db_name']}"
    )
    
    print(f"Executing restore on staging... (This might take a while)")
    try:
        conn.run(restore_cmd)
        print("Restore successful.")
    except UnexpectedExit as e:
        print(f"Restore failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

# ... (inside main) ...

def main():
    parser = argparse.ArgumentParser(description="Database Backup & Restore Tool")
    parser.add_argument('action', choices=['backup', 'download', 'upload', 'restore', 'full', 'test', 'backup_staging', 'download_staging'], 
                        help="Action to perform")
    parser.add_argument('--config', default='config.yaml', help="Path to config file")
    parser.add_argument('--file', help="Specific filename to use. Optional.")
    parser.add_argument('--clean', action='store_true', help="[Restore/Full] Drop and recreate 'public' schema before restoring. WARNING: Destructive!")
    
    args = parser.parse_args()
    config = load_config(args.config)
    
    # ... (Filename logic unchanged) ...

    if args.action == 'test':
        test_connections(config)
    elif args.action == 'backup':
        backup_prod(config, filename)
    elif args.action == 'download':
        download_backup(config, filename)
    elif args.action == 'upload':
        upload_backup(config, filename)
    elif args.action == 'restore':
        restore_staging(config, filename, clean=args.clean)
    elif args.action == 'backup_staging':
        backup_staging(config, filename)
    elif args.action == 'download_staging':
        download_staging(config, filename)
    elif args.action == 'full':
        print(f"Starting FULL pipeline with filename: {filename}")
        backup_prod(config, filename)
        download_backup(config, filename)
        upload_backup(config, filename)
        restore_staging(config, filename, clean=args.clean) # Pass clean flag to full as well

def test_connections(config):
    print("--- Testing Connections ---")
    
    # Test Production
    try:
        print(f"Connecting to Production ({config['production']['host']})...")
        prod_conn = get_connection(config['production'])
        result = prod_conn.run("ls -la", hide=True)
        print(f"  [SSH] OK! Output length: {len(result.stdout)} bytes")
        
        # Test DB
        print(f"  [DB] Testing PostgreSQL connection...")
        prod_conf = config['production']
        db_check_cmd = f"docker exec {prod_conf['docker_container']} psql -U {prod_conf['db_user']} -d {prod_conf['db_name']} -c \"SELECT 1;\""
        prod_conn.run(db_check_cmd, hide=True)
        print(f"  [DB] OK! Database '{prod_conf['db_name']}' is accessible.")
        
        prod_conn.close()
    except Exception as e:
        print(f"  [ERROR] Production Failed: {e}")

    # Test Staging
    try:
        print(f"Connecting to Staging ({config['staging']['host']})...")
        staging_conn = get_connection(config['staging'])
        result = staging_conn.run("ls -la", hide=True)
        print(f"  [SSH] OK! Output length: {len(result.stdout)} bytes")
        
        # Test DB
        print(f"  [DB] Testing PostgreSQL connection...")
        staging_conf = config['staging']
        db_check_cmd = f"docker exec {staging_conf['docker_container']} psql -U {staging_conf['db_user']} -d {staging_conf['db_name']} -c \"SELECT 1;\""
        staging_conn.run(db_check_cmd, hide=True)
        print(f"  [DB] OK! Database '{staging_conf['db_name']}' is accessible.")
        
        staging_conn.close()
    except Exception as e:
        print(f"  [ERROR] Staging Failed: {e}")

def find_latest_backup(backup_dir, base_filename):
    """Finds the most recent backup file in the directory matching the base filename pattern."""
    if not os.path.exists(backup_dir):
        return None
    
    # Base pattern (e.g. backup_*.sql.gz)
    # This is a bit naiive, assuming structure [base]_[timestamp].[ext]
    # We'll just look for files that start with the base name (minus extension)
    
    if '.' in base_filename:
        prefix = base_filename.split('.', 1)[0]
        extension = base_filename.split('.', 1)[1]
    else:
        prefix = base_filename
        extension = ""
        
    candidates = []
    for f in os.listdir(backup_dir):
        if f.startswith(prefix) and (extension in f if extension else True):
            candidates.append(f)
            
    if not candidates:
        return None
        
    # Sort by name (timestamp is increasing, so last is newest) or actual mtime
    candidates.sort(reverse=True)
    return candidates[0]

def find_latest_remote_backup(config, base_filename):
    """Finds the most recent backup file on the REMOTE Production server."""
    prod_conf = config['production']
    conn = get_connection(prod_conf)
    
    # Base pattern logic
    if '.' in base_filename:
        prefix = base_filename.split('.', 1)[0]
    else:
        prefix = base_filename
        
    # List files in /tmp/ matching pattern
    # We use a simple command to list and sort by time
    cmd = f"ls -t /tmp/ | grep '{prefix}' | head -n 1"
    
    try:
        result = conn.run(cmd, hide=True)
        filename = result.stdout.strip()
        if filename:
            return filename
        return None
    except Exception:
        return None
    finally:
        conn.close()

def find_latest_remote_staging_backup(config, base_filename):
    """Finds the most recent backup file on the REMOTE Staging server."""
    staging_conf = config['staging']
    conn = get_connection(staging_conf)
    
    # Base pattern logic
    # Staging files are prefixed with 'staging_' in logic: filename = f"staging_{filename}"
    
    if '.' in base_filename:
        prefix = base_filename.split('.', 1)[0]
    else:
        prefix = base_filename
        
    search_prefix = f"staging_{prefix}"
    
    # List files in /tmp/ matching pattern
    cmd = f"ls -t /tmp/ | grep '{search_prefix}' | head -n 1"
    
    try:
        result = conn.run(cmd, hide=True)
        filename = result.stdout.strip()
        if filename:
            return filename
        return None
    except Exception:
        return None
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Database Backup & Restore Tool")
    parser.add_argument('action', choices=['backup', 'download', 'upload', 'restore', 'full', 'test', 'backup_staging', 'download_staging'], 
                        help="Action to perform")
    parser.add_argument('--config', default='config.yaml', help="Path to config file")
    parser.add_argument('--file', help="Specific filename to use. Optional.")
    parser.add_argument('--clean', action='store_true', help="[Restore/Full] Drop and recreate 'public' schema before restoring. WARNING: Destructive!")
    
    args = parser.parse_args()
    config = load_config(args.config)
    
    # Determine Filename
    filename = None
    
    if args.file:
        filename = args.file
    else:
        # Default behavior depends on action
        base_name = config['local'].get('backup_filename', 'backup.sql.gz')
        
        if args.action in ['backup', 'full', 'backup_staging']:
            # ALWAYS New file for backup creation
            filename = get_timestamped_filename(base_name)
            # If backing up staging, maybe prefix differently to differentiate?
            if args.action == 'backup_staging':
                filename = f"staging_{filename}"
        
        elif args.action == 'download':
            # For download, we look at REMOTE PROD
            print(f"No --file specified. Looking for latest backup on REMOTE Production...")
            latest = find_latest_remote_backup(config, base_name)
            if latest:
                 filename = latest
                 print(f"Found latest remote backup: {filename}")
            else:
                 print(f"Error: Could not find any backup files matching '{base_name}' on Remote Production /tmp/")
                 sys.exit(1)

        elif args.action == 'download_staging':
             # Auto-detect latest staging file
             print("No --file specified. Looking for latest backup on REMOTE Staging...")
             latest = find_latest_remote_staging_backup(config, base_name)
             if latest:
                 filename = latest
                 print(f"Found latest remote staging backup: {filename}")
             else:
                 print(f"Error: Could not find any backup files matching 'staging_{base_name}' on Remote Staging /tmp/")
                 sys.exit(1)
             
        elif args.action in ['upload', 'restore']:
            # Seek the LATEST file for operations on existing data (LOCALLY)
            print(f"No --file specified. Looking for latest backup in {config['local']['backup_dir']}...")
            latest = find_latest_backup(config['local']['backup_dir'], base_name)
            if latest:
                filename = latest
                print(f"Found latest local backup: {filename}")
            else:
                print(f"Error: Could not find any existing backup files matching '{base_name}' in {config['local']['backup_dir']}")
                print("Please run 'backup' first or specify a file with --file")
                sys.exit(1)
        elif args.action == 'test':
             pass

    if args.action == 'test':
        test_connections(config)
    elif args.action == 'backup':
        backup_prod(config, filename)
    elif args.action == 'download':
        download_backup(config, filename)
    elif args.action == 'upload':
        upload_backup(config, filename)
    elif args.action == 'restore':
        restore_staging(config, filename, clean=args.clean)
    elif args.action == 'backup_staging':
        backup_staging(config, filename)
    elif args.action == 'download_staging':
        download_staging(config, filename)
    elif args.action == 'full':
        print(f"Starting FULL pipeline with filename: {filename}")
        backup_prod(config, filename)
        download_backup(config, filename)
        upload_backup(config, filename)
        restore_staging(config, filename, clean=args.clean)

if __name__ == "__main__":
    main()
