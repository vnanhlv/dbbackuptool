import argparse
import yaml
import os
import sys
import datetime
from fabric import Connection

# Vietnamese comment: Load configuration
def load_config(config_path=None):
    if config_path is None:
        # Default to config.yaml in the same directory as the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.yaml')

    if not os.path.exists(config_path):
        if os.path.exists('config.yaml'):
            config_path = 'config.yaml'
        else:
            print(f"Error: Config file '{config_path}' not found.")
            sys.exit(1)
            
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

# Vietnamese comment: Tạo kết nối SSH
def get_connection(server_config):
    connect_kwargs = {}
    if 'ssh_key_path' in server_config and server_config['ssh_key_path']:
        connect_kwargs["key_filename"] = server_config['ssh_key_path']
    
    if 'ssh_passphrase' in server_config and server_config['ssh_passphrase']:
        connect_kwargs['passphrase'] = server_config['ssh_passphrase']

    print(f"Connecting to {server_config['user']}@{server_config['host']}...")
    return Connection(
        host=server_config['host'],
        user=server_config['user'],
        port=server_config.get('port', 22),
        connect_kwargs=connect_kwargs
    )

def main():
    parser = argparse.ArgumentParser(description="Log Downloader Tool")
    parser.add_argument('--config', help="Path to config file")
    args = parser.parse_args()

    config = load_config(args.config)
    
    server_conf = config['server']
    log_conf = config['logs']
    settings = config.get('settings', {})
    
    # Check local download directory
    local_dir = log_conf.get('local_path', 'logs')
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
        print(f"Created local directory: {local_dir}")

    remote_dir = log_conf['remote_path']
    patterns = log_conf.get('import_patterns', ['*.1.log', '*.2.log', '*.3.log', '*.4.log', '*.5.log'])
    
    conn = get_connection(server_conf)
    
    try:
        # 1. List files
        # Vietnamese comment: Liệt kê file trên server
        print(f"Scanning remote directory: {remote_dir}")
        result = conn.run(f"ls -1 {remote_dir}", hide=True)
        files = result.stdout.strip().split('\n')
        
        # 2. Filter files
        to_download = []
        for f in files:
            f = f.strip()
            if not f: continue
            
            # Check if file matches any pattern
            match = False
            for p in patterns:
                # Convert glob pattern to simple string check if possible
                if p.startswith('*'):
                    suffix = p[1:]
                    if f.endswith(suffix):
                        match = True
                        break
                elif p == f:
                    match = True
                    break
            
            if match:
                to_download.append(f)
        
        print(f"Found {len(to_download)} files to download: {to_download}")
        
        # 3. Download and Delete
        for filename in to_download:
            remote_file = f"{remote_dir}/{filename}"
            local_file = os.path.join(local_dir, filename)
            
            print(f"Downloading {filename}...")
            try:
                conn.get(remote_file, local_file)
                print(f"  [OK] Downloaded to {local_file}")
                
                # Check existence
                if os.path.exists(local_file):
                    if settings.get('after_download') == 'delete':
                        # Vietnamese comment: Xóa file sau khi tải xong nếu config cho phép
                        print(f"  [DELETE] Removing remote file {filename}...")
                        conn.run(f"rm {remote_file}")
                        print("  [OK] Deleted.")
                    else:
                        print("  [KEEP] Keeping remote file (config not set to delete).")
                else:
                    print("  [ERROR] Local file missing. Skipping delete.")
                    
            except Exception as e:
                print(f"  [ERROR] Failed to download {filename}: {e}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
