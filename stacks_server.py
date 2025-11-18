#!/usr/bin/env python3
"""
Stacks - Download Queue Manager for Anna's Archive
"""

import json
import threading
import time
import sys
import logging
import secrets
import string
import bcrypt
import os
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import yaml

# Import downloader
import stacks_downloader

# Constants for paths (not configurable via config file)
DOWNLOAD_PATH = "/opt/stacks/download"
INCOMPLETE_PATH = "/opt/stacks/download/incomplete"
QUEUE_STORAGE = "/opt/stacks/config/queue.json"
LOG_PATH = "/opt/stacks/logs"
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
FAST_DOWNLOAD_API_URL = "https://annas-archive.org/dyn/api/fast_download.json"

# Default credentials
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "stacks"

# Rate limiting for login
login_attempts = {}
login_lockouts = {}


def generate_api_key():
    """Generate a secure 32-character alphanumeric API key"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))


def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password, hashed):
    """Verify a password against a bcrypt hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def is_valid_bcrypt_hash(hash_string):
    """Check if a string looks like a valid bcrypt hash"""
    if not hash_string:
        return False
    # Bcrypt hashes start with $2a$, $2b$, or $2y$ and are 60 characters
    return (hash_string.startswith(('$2a$', '$2b$', '$2y$')) and len(hash_string) == 60)


def check_rate_limit(ip):
    """Check if IP is rate limited. Returns (allowed, message)"""
    # Check if locked out
    if ip in login_lockouts:
        lockout_until = login_lockouts[ip]
        if datetime.now() < lockout_until:
            remaining = int((lockout_until - datetime.now()).total_seconds() / 60)
            return False, f"Too many failed attempts. Try again in {remaining} minutes."
        else:
            # Lockout expired
            del login_lockouts[ip]
            if ip in login_attempts:
                del login_attempts[ip]
    
    # Check attempts
    if ip not in login_attempts:
        login_attempts[ip] = []
    
    # Clean old attempts (older than 10 minutes)
    cutoff = datetime.now() - timedelta(minutes=10)
    login_attempts[ip] = [t for t in login_attempts[ip] if t > cutoff]
    
    if len(login_attempts[ip]) >= 5:
        # Lock out for 10 minutes
        login_lockouts[ip] = datetime.now() + timedelta(minutes=10)
        return False, "Too many failed attempts. Try again in 10 minutes."
    
    return True, None


def record_failed_attempt(ip):
    """Record a failed login attempt"""
    if ip not in login_attempts:
        login_attempts[ip] = []
    login_attempts[ip].append(datetime.now())


def clear_attempts(ip):
    """Clear login attempts for IP after successful login"""
    if ip in login_attempts:
        del login_attempts[ip]
    if ip in login_lockouts:
        del login_lockouts[ip]


class Config:
    """Configuration loader with live update support"""
    def __init__(self, config_path="/opt/stacks/config/config.yaml"):
        self.config_path = config_path
        self.lock = threading.Lock()
        self.load()
        self.ensure_api_key()
        self.ensure_session_secret()
        self.ensure_login_credentials()
    
    def load(self):
        """Load configuration from file"""
        with self.lock:
            with open(self.config_path, 'r') as f:
                self.data = yaml.safe_load(f)
    
    def save(self):
        """Save configuration to file"""
        with self.lock:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)
    
    def ensure_api_key(self):
        """Ensure API key exists, generate if not present"""
        api_key = self.get('api', 'key')
        if not api_key:
            new_key = generate_api_key()
            self.set('api', 'key', value=new_key)
            self.save()
            logger = logging.getLogger('config')
            logger.info("Generated new API key")
    
    def ensure_session_secret(self):
        """Ensure session secret exists, generate if not present"""
        session_secret = self.get('api', 'session_secret')
        if not session_secret:
            new_secret = generate_api_key()  # Same format, 32 chars
            self.set('api', 'session_secret', value=new_secret)
            self.save()
            logger = logging.getLogger('config')
            logger.info("Generated new session secret")
    
    def ensure_login_credentials(self):
        """Ensure login credentials exist, generate from env vars or defaults"""
        logger = logging.getLogger('config')
        username = self.get('login', 'username')
        password_hash = self.get('login', 'password')
        
        # Check for RESET_ADMIN environment variable
        reset_admin = os.environ.get('RESET_ADMIN', '').lower() == 'true'
        
        # Determine if we need to reset/set credentials
        needs_reset = (
            reset_admin or
            not username or
            not password_hash or
            not is_valid_bcrypt_hash(password_hash)
        )
        
        if needs_reset:
            # Get credentials from environment or use defaults
            env_username = os.environ.get('USERNAME', DEFAULT_USERNAME)
            env_password = os.environ.get('PASSWORD', DEFAULT_PASSWORD)
            
            # Hash the password
            hashed = hash_password(env_password)
            
            # Save to config
            self.set('login', 'username', value=env_username)
            self.set('login', 'password', value=hashed)
            self.save()
            
            if reset_admin:
                logger.warning("RESET_ADMIN=true detected - Admin password has been reset")
            elif not username or not password_hash:
                logger.info(f"Initialized login credentials - username: {env_username}")
            else:
                logger.warning("Invalid password hash detected - credentials reset from environment")
    
    def get(self, *keys, default=None):
        """Get nested config value"""
        with self.lock:
            value = self.data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return default
                if value is None:
                    return default
            return value
    
    def set(self, *keys, value):
        """Set nested config value"""
        with self.lock:
            # Navigate to parent
            data = self.data
            for key in keys[:-1]:
                if key not in data:
                    data[key] = {}
                data = data[key]
            # Set value
            data[keys[-1]] = value
    
    def get_all(self):
        """Get entire config as dict"""
        with self.lock:
            return self.data.copy()


class DownloadQueue:
    def __init__(self, config):
        self.config = config
        self.storage_file = Path(QUEUE_STORAGE)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.queue = []
        self.current_download = None
        self.history = []
        self.lock = threading.Lock()
        self.logger = logging.getLogger('queue')
        self.load()
    
    def load(self):
        """Load queue from disk"""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    self.queue = data.get('queue', [])
                    self.history = data.get('history', [])
                self.logger.info(f"Loaded queue: {len(self.queue)} items, {len(self.history)} history")
            except Exception as e:
                self.logger.error(f"Failed to load queue: {e}")
    
    def save(self):
        """Save queue to disk"""
        try:
            max_history = self.config.get('queue', 'max_history', default=100)
            history_to_save = self.history if max_history == 0 else self.history[-max_history:]
            
            with open(self.storage_file, 'w') as f:
                json.dump({
                    'queue': self.queue,
                    'history': history_to_save
                }, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save queue: {e}")
    
    def add(self, md5, title=None, source=None):
        """Add item to queue"""
        with self.lock:
            # Check if in queue
            if any(item['md5'] == md5 for item in self.queue):
                return False, "Already in queue"
            
            # Check if currently downloading
            if self.current_download and self.current_download['md5'] == md5:
                return False, "Currently downloading"
            
            # Check if recently SUCCESSFULLY downloaded (allow retry of failures)
            if any(item['md5'] == md5 and item.get('success', False) for item in self.history[-50:]):
                return False, "Recently downloaded"
            
            item = {
                'md5': md5,
                'title': title or 'Unknown',
                'source': source,
                'added_at': datetime.now().isoformat(),
                'status': 'queued'
            }
            
            self.queue.append(item)
            self.save()
            self.logger.info(f"Added to queue: {title} ({md5})")
            return True, "Added to queue"
    
    def get_next(self):
        """Get next item from queue"""
        with self.lock:
            if self.queue:
                return self.queue.pop(0)
            return None
    
    def mark_complete(self, md5, success, filepath=None, error=None, used_fast_download=False):
        """Mark download as complete"""
        with self.lock:
            item = {
                'md5': md5,
                'title': self.current_download.get('title', 'Unknown') if self.current_download else 'Unknown',
                'completed_at': datetime.now().isoformat(),
                'success': success,
                'filepath': str(filepath) if filepath else None,
                'error': error,
                'used_fast_download': used_fast_download
            }
            self.history.append(item)
            self.current_download = None
            self.save()
            
            if success:
                method = "fast download" if used_fast_download else "mirror"
                self.logger.info(f"Download complete ({method}): {item['title']}")
            else:
                self.logger.warning(f"Download failed: {item['title']} - {error}")
    
    def get_status(self):
        """Get current queue status"""
        with self.lock:
            return {
                'current': self.current_download,
                'queue': self.queue.copy(),
                'queue_size': len(self.queue),
                'recent_history': self.history[-10:][::-1]
            }
    
    def remove_from_queue(self, md5):
        """Remove item from queue"""
        with self.lock:
            original_length = len(self.queue)
            self.queue = [item for item in self.queue if item['md5'] != md5]
            removed = original_length != len(self.queue)
            if removed:
                self.save()
                self.logger.info(f"Removed from queue: {md5}")
            return removed
    
    def clear_queue(self):
        """Clear all items from queue"""
        with self.lock:
            count = len(self.queue)
            self.queue = []
            self.save()
            self.logger.info(f"Cleared queue: {count} items removed")
            return count
    
    def clear_history(self):
        """Clear all items from history"""
        with self.lock:
            count = len(self.history)
            self.history = []
            self.save()
            self.logger.info(f"Cleared history: {count} items removed")
            return count
    
    def retry_failed(self, md5):
        """Retry a failed download by removing from history and re-adding to queue"""
        with self.lock:
            # Find the failed item in history
            failed_item = None
            for item in self.history:
                if item['md5'] == md5 and not item.get('success', False):
                    failed_item = item
                    break
            
            if not failed_item:
                return False, "Item not found in failed history"
            
            # Remove from history
            self.history = [item for item in self.history if item['md5'] != md5]
            
            # Add back to queue
            new_item = {
                'md5': md5,
                'title': failed_item.get('title', 'Unknown'),
                'source': 'retry',
                'added_at': datetime.now().isoformat(),
                'status': 'queued'
            }
            
            self.queue.append(new_item)
            self.save()
            self.logger.info(f"Retrying failed download: {failed_item.get('title')} ({md5})")
            return True, "Added to queue for retry"


class DownloadWorker:
    def __init__(self, queue, config):
        self.queue = queue
        self.config = config
        self.running = False
        self.thread = None
        self.logger = logging.getLogger('worker')
        
        # Progress callback to update current download
        def progress_callback(progress):
            if self.queue.current_download:
                with self.queue.lock:
                    self.queue.current_download.update({
                        'progress': progress
                    })
        
        # Initialize downloader
        self.progress_callback = progress_callback
        self.recreate_downloader()
    
    def recreate_downloader(self):
        """Recreate downloader with current config"""
        # Get fast download config from main config
        fast_config = {
            'enabled': self.config.get('fast_download', 'enabled', default=False),
            'key': self.config.get('fast_download', 'key'),
            'api_url': FAST_DOWNLOAD_API_URL,
            'path_index': 0,
            'domain_index': 0
        }
        
        self.downloader = stacks_downloader.AnnaDownloader(
            output_dir=DOWNLOAD_PATH,
            incomplete_dir=INCOMPLETE_PATH,
            progress_callback=self.progress_callback,
            fast_download_config=fast_config
        )
        
        # Test fast download key if enabled and key is present
        if fast_config['enabled'] and fast_config['key']:
            self.logger.info("Testing fast download key...")
            try:
                # Use refresh method with force=True to bypass cooldown on startup
                success = self.downloader.refresh_fast_download_info(force=True)
                
                if success:
                    info = self.downloader.get_fast_download_info()
                    self.logger.info(f"Fast download key valid - {info.get('downloads_left')}/{info.get('downloads_per_day')} downloads available")
                else:
                    self.logger.warning("Fast download key test failed")
            except Exception as e:
                self.logger.error(f"Failed to test fast download key: {e}")
        
        self.logger.info("Downloader recreated with updated config")
    
    def update_config(self):
        """Update downloader with new config (called when config changes)"""
        self.recreate_downloader()
    
    def start(self):
        """Start worker thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.thread.start()
            self.logger.info("Download worker started")
    
    def stop(self):
        """Stop worker thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.logger.info("Download worker stopped")
    
    def get_fast_download_info(self):
        """Get current fast download status"""
        return self.downloader.get_fast_download_info()
    
    def refresh_fast_download_info_if_stale(self):
        """Refresh fast download info if it's been more than an hour"""
        return self.downloader.refresh_fast_download_info(force=False)
    
    def _worker_loop(self):
        """Main worker loop"""
        delay = self.config.get('downloads', 'delay', default=2)
        resume_attempts = self.config.get('downloads', 'resume_attempts', default=3)
        
        while self.running:
            item = self.queue.get_next()
            
            if item is None:
                time.sleep(1)
                continue
            
            # Set as current download
            with self.queue.lock:
                self.queue.current_download = item
                self.queue.current_download['status'] = 'downloading'
                self.queue.current_download['started_at'] = datetime.now().isoformat()
                self.queue.current_download['progress'] = {
                    'total_size': 0,
                    'downloaded': 0,
                    'percent': 0
                }
            
            self.logger.info(f"Starting download: {item['title']} ({item['md5']})")
            
            try:
                # Pass the title from the queue item to ensure correct filename
                # Now receives tuple: (success, used_fast_download)
                success, used_fast_download = self.downloader.download(
                    item['md5'], 
                    resume_attempts=resume_attempts,
                    title_override=item.get('title')
                )
                
                if success:
                    self.queue.mark_complete(item['md5'], True, used_fast_download=used_fast_download)
                else:
                    self.queue.mark_complete(item['md5'], False, error="Download failed")
                
            except Exception as e:
                self.logger.error(f"Download error: {item['title']} - {e}")
                self.queue.mark_complete(item['md5'], False, error=str(e))
            
            # Rate limiting
            if self.queue.queue:
                time.sleep(delay)


# Flask app
app = Flask(__name__, 
            template_folder='/opt/stacks/web',
            static_folder='/opt/stacks/web',
            static_url_path='')
CORS(app, supports_credentials=True)

# Global instances
config = None
queue = None
worker = None

logger = logging.getLogger('api')


def require_login(f):
    """Decorator to require login for web interface"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def require_auth(f):
    """Decorator to require either session auth OR API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check session first (for web UI)
        if session.get('logged_in'):
            return f(*args, **kwargs)
        
        # Check API key (for external tools)
        provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if provided_key:
            valid_key = config.get('api', 'key')
            if provided_key == valid_key:
                return f(*args, **kwargs)
        
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    return decorated_function


def require_session_only(f):
    """Decorator to require session auth ONLY (not API key)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Only allow session authentication
        if session.get('logged_in'):
            return f(*args, **kwargs)
        
        return jsonify({'success': False, 'error': 'Session authentication required'}), 401
    
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if session.get('logged_in'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        data = request.json
        username = data.get('username', '')
        password = data.get('password', '')
        ip = request.remote_addr
        
        # Check rate limit
        allowed, message = check_rate_limit(ip)
        if not allowed:
            return jsonify({'success': False, 'error': message}), 429
        
        # Verify credentials
        stored_username = config.get('login', 'username')
        stored_password = config.get('login', 'password')
        
        if username == stored_username and verify_password(password, stored_password):
            # Success
            clear_attempts(ip)
            session['logged_in'] = True
            session.permanent = True
            logger.info(f"Successful login from {ip}")
            return jsonify({'success': True})
        else:
            # Failed
            record_failed_attempt(ip)
            logger.warning(f"Failed login attempt from {ip}")
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout handler"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@require_login
def index():
    """Web interface - requires login"""
    return render_template('index.html')


@app.route('/api/status')
@require_auth
def api_status():
    """Get current status"""
    status = queue.get_status()
    
    # Refresh fast download info if stale (respects 1-hour cooldown)
    worker.refresh_fast_download_info_if_stale()
    
    # Add fast download info
    fast_info = worker.get_fast_download_info()
    status['fast_download'] = fast_info
    
    return jsonify(status)

@app.get("/api/health")
def health():
    logger.debug("Health endpoint checked")
    return {"status": "ok"}

@app.route('/api/version')
def api_version():
    """Get current version"""
    with open("VERSION") as f:
        version = f.read().strip()
    return jsonify({"version": version})

@app.route('/api/key')
@require_session_only
def api_key_info():
    """Get API key (session auth only - for web UI)"""
    return jsonify({'api_key': config.get('api', 'key')})

@app.route('/api/queue/add', methods=['POST'])
@require_auth
def api_queue_add():
    """Add item to queue"""
    data = request.json
    md5 = data.get('md5')
    
    if not md5:
        return jsonify({'success': False, 'error': 'MD5 required'}), 400
    
    # Validate MD5
    extracted_md5 = stacks_downloader.extract_md5(md5)
    
    if not extracted_md5:
        return jsonify({'success': False, 'error': 'Invalid MD5 format'}), 400
    
    # Add to queue
    success, message = queue.add(
        extracted_md5,
        title=data.get('title'),
        source=data.get('source')
    )
    
    return jsonify({
        'success': success,
        'message': message,
        'md5': extracted_md5
    })


@app.route('/api/queue/remove', methods=['POST'])
@require_auth
def api_queue_remove():
    """Remove item from queue"""
    data = request.json
    md5 = data.get('md5')
    
    if not md5:
        return jsonify({'success': False, 'error': 'MD5 required'}), 400
    
    removed = queue.remove_from_queue(md5)
    
    return jsonify({
        'success': removed,
        'message': 'Removed from queue' if removed else 'Not found in queue'
    })


@app.route('/api/queue/clear', methods=['POST'])
@require_auth
def api_queue_clear():
    """Clear entire queue"""
    count = queue.clear_queue()
    return jsonify({
        'success': True,
        'message': f'Cleared {count} item(s) from queue'
    })


@app.route('/api/history/clear', methods=['POST'])
@require_auth
def api_history_clear():
    """Clear entire history"""
    count = queue.clear_history()
    return jsonify({
        'success': True,
        'message': f'Cleared {count} item(s) from history'
    })


@app.route('/api/history/retry', methods=['POST'])
@require_auth
def api_history_retry():
    """Retry a failed download"""
    data = request.json
    md5 = data.get('md5')
    
    if not md5:
        return jsonify({'success': False, 'error': 'MD5 required'}), 400
    
    success, message = queue.retry_failed(md5)
    
    return jsonify({
        'success': success,
        'message': message
    })


@app.route('/api/config', methods=['GET'])
@require_auth
def api_config_get():
    """Get current configuration"""
    import copy
    config_data = copy.deepcopy(config.get_all())
    # Mask sensitive data
    if 'api' in config_data and 'key' in config_data['api']:
        config_data['api']['key'] = '***MASKED***'
    if 'login' in config_data and 'password' in config_data['login']:
        config_data['login']['password'] = '***MASKED***'
    return jsonify(config_data)


@app.route('/api/config', methods=['POST'])
@require_auth
def api_config_update():
    """Update configuration"""
    data = request.json
    logger = logging.getLogger('api')
    
    try:
        # Update each provided config value
        if 'downloads' in data:
            if 'delay' in data['downloads']:
                config.set('downloads', 'delay', value=int(data['downloads']['delay']))
            if 'retry_count' in data['downloads']:
                config.set('downloads', 'retry_count', value=int(data['downloads']['retry_count']))
            if 'resume_attempts' in data['downloads']:
                config.set('downloads', 'resume_attempts', value=int(data['downloads']['resume_attempts']))
        
        if 'fast_download' in data:
            if 'enabled' in data['fast_download']:
                config.set('fast_download', 'enabled', value=bool(data['fast_download']['enabled']))
            if 'key' in data['fast_download']:
                key_value = data['fast_download']['key']
                # Allow null/empty to clear the key
                if key_value == '' or key_value is None:
                    key_value = None
                config.set('fast_download', 'key', value=key_value)
        
        if 'queue' in data:
            if 'max_history' in data['queue']:
                config.set('queue', 'max_history', value=int(data['queue']['max_history']))
        
        if 'logging' in data:
            if 'level' in data['logging']:
                new_level = data['logging']['level'].upper()
                if new_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
                    config.set('logging', 'level', value=new_level)
                    # Update logging level immediately
                    setup_logging(config)
        
        # Handle login credentials update (only if session authenticated)
        if 'login' in data and session.get('logged_in'):
            if 'username' in data['login']:
                new_username = data['login']['username']
                if new_username:
                    config.set('login', 'username', value=new_username)
            
            if 'new_password' in data['login']:
                new_password = data['login']['new_password']
                if new_password:
                    hashed = hash_password(new_password)
                    config.set('login', 'password', value=hashed)
                    logger.info("Password updated via settings")
        
        # Save config to disk
        config.save()
        
        # Update worker with new config (recreate downloader)
        worker.update_config()
        
        logger.info("Configuration updated successfully")
        
        import copy
        config_data = copy.deepcopy(config.get_all())
        # Mask sensitive data
        if 'api' in config_data and 'key' in config_data['api']:
            config_data['api']['key'] = '***MASKED***'
        if 'login' in config_data and 'password' in config_data['login']:
            config_data['login']['password'] = '***MASKED***'
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated',
            'config': config_data
        })
        
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/config/test_key', methods=['POST'])
@require_auth
def api_config_test_key():
    """Test fast download key and update cached info"""
    data = request.json
    test_key = data.get('key')
    
    if not test_key:
        return jsonify({
            'success': False,
            'error': 'No key provided'
        }), 400
    
    try:
        import requests
        
        # Use a known valid MD5 for testing
        test_md5 = 'd6e1dc51a50726f00ec438af21952a45'
        
        response = requests.get(
            FAST_DOWNLOAD_API_URL,
            params={
                'md5': test_md5,
                'key': test_key
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('download_url'):
                info = data.get('account_fast_download_info', {})
                
                # Update the worker's cached info with timestamp
                if worker.downloader.fast_download_key == test_key:
                    worker.downloader.fast_download_info.update({
                        'available': True,
                        'downloads_left': info.get('downloads_left'),
                        'downloads_per_day': info.get('downloads_per_day'),
                        'recently_downloaded_md5s': info.get('recently_downloaded_md5s', []),
                        'last_refresh': time.time()
                    })
                
                return jsonify({
                    'success': True,
                    'message': 'Key is valid',
                    'downloads_left': info.get('downloads_left'),
                    'downloads_per_day': info.get('downloads_per_day')
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No download URL in response'
                }), 400
        elif response.status_code == 401:
            return jsonify({
                'success': False,
                'error': 'Invalid secret key'
            }), 401
        elif response.status_code == 403:
            return jsonify({
                'success': False,
                'error': 'Not a member'
            }), 403
        else:
            return jsonify({
                'success': False,
                'error': f'API returned status {response.status_code}'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Connection failed: {str(e)}'
        }), 500


@app.route('/api/key/regenerate', methods=['POST'])
@require_session_only
def api_key_regenerate():
    """Regenerate API key"""
    try:
        new_key = generate_api_key()
        config.set('api', 'key', value=new_key)
        config.save()
        
        logger.info("API key regenerated")
        
        return jsonify({
            'success': True,
            'message': 'New API key generated',
            'api_key': new_key
        })
    except Exception as e:
        logger.error(f"Failed to regenerate API key: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


def setup_logging(config):
    """Setup logging configuration"""
    log_level = getattr(logging, config.get('logging', 'level', default='WARNING'))
    log_path = Path(LOG_PATH)
    
    # Create log directory
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Log file with date
    log_file = log_path / f"log-{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()
    
    # Create new handlers
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Configure werkzeug (Flask) logger - silence all output including startup
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)  # Only errors from Flask
    werkzeug_logger.propagate = False  # Don't propagate to root logger
    
    # Remove all werkzeug handlers
    for handler in werkzeug_logger.handlers[:]:
        werkzeug_logger.removeHandler(handler)
    
    # Add a silent handler for werkzeug errors only
    werkzeug_handler = logging.StreamHandler(sys.stdout)
    werkzeug_handler.setLevel(logging.ERROR)
    werkzeug_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    werkzeug_logger.addHandler(werkzeug_handler)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Stacks - Anna's Archive Download Manager")
    parser.add_argument('-c', '--config', default='/opt/stacks/config/config.yaml',
                       help='Path to config file')
    
    args = parser.parse_args()
    
    # Load config
    global config, queue, worker
    config = Config(args.config)
    
    # Configure Flask session
    app.secret_key = config.get('api', 'session_secret')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30 days
    
    # Configure CORS to allow credentials
    CORS(app, supports_credentials=True, origins=['*'])

    # Setup logging
    setup_logging(config)
    logger = logging.getLogger('main')
    
    # Log login credentials
    username = config.get('login', 'username')
    logger.info(f"Login username: {username}")
    
    # Log fast download status
    fast_enabled = config.get('fast_download', 'enabled', default=False)
    fast_key = config.get('fast_download', 'key')
    if fast_enabled and fast_key:
        logger.info("Fast download: ENABLED")
    elif fast_enabled and not fast_key:
        logger.warning("Fast download: ENABLED but no key configured")
    else:
        logger.info("Fast download: DISABLED")
    
    # Create queue
    queue = DownloadQueue(config)
    
    # Start worker
    worker = DownloadWorker(queue, config)
    worker.start()
    
    # Get config
    host = config.get('server', 'host')
    port = config.get('server', 'port')
    
    logger.info(f"Starting Stacks server on {host}:{port}")
    
    # Silence Flask startup completely
    import os
    cli = sys.modules['flask.cli']
    cli.show_server_banner = lambda *x: None
    
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        worker.stop()
        sys.exit(0)


if __name__ == '__main__':
    main()
