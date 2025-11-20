import logging
import time
from flask import (
    jsonify,
    request,
    session,
    current_app,
)
from stacks.constants import FAST_DOWNLOAD_API_URL
from . import api_bp
from stacks.utils.logutils import setup_logging
from stacks.security.auth import (
    require_auth,
    hash_password,
)

logger = logging.getLogger("api")

@api_bp.route('/api/config/test_flaresolverr', methods=['POST'])
@require_auth
def api_config_test_flaresolverr():
    """Test FlareSolverr connection"""
    data = request.json
    test_url = data.get('url', 'http://localhost:8191')
    timeout = data.get('timeout', 10)
    
    if not test_url:
        return jsonify({
            'success': False,
            'error': 'No URL provided'
        }), 400
    
    try:
        import requests
        
        # Try to connect to FlareSolverr's health endpoint
        response = requests.get(test_url, timeout=timeout)
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'message': 'FlareSolverr is online and responding',
                'status_code': response.status_code
            })
        else:
            return jsonify({
                'success': False,
                'error': f'FlareSolverr returned status {response.status_code}'
            }), 400
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': f'Connection timeout after {timeout} seconds'
        }), 408
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Could not connect to FlareSolverr. Is it running?'
        }), 503
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Connection failed: {str(e)}'
        }), 500
    
@api_bp.route('/api/config/test_key', methods=['POST'])
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
                worker = current_app.stacks_worker
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
    
@api_bp.route('/api/config', methods=['POST'])
@require_auth
def api_config_update():
    """Update configuration"""
    data = request.json
    logger = logging.getLogger('api')
    config = current_app.stacks_config

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
        if 'flaresolverr' in data:
            if 'enabled' in data['flaresolverr']:
                config.set('flaresolverr', 'enabled', value=bool(data['flaresolverr']['enabled']))
            if 'url' in data['flaresolverr']:
                url_value = data['flaresolverr']['url']
                # Allow null/empty to set default
                if not url_value:
                    url_value = 'http://localhost:8191'
                config.set('flaresolverr', 'url', value=url_value)
            if 'timeout' in data['flaresolverr']:
                timeout_value = int(data['flaresolverr']['timeout'])
                # Clamp between 10-300 seconds
                if timeout_value < 10:
                    timeout_value = 10
                if timeout_value > 300:
                    timeout_value = 300
                config.set('flaresolverr', 'timeout', value=timeout_value)
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
        worker = current_app.stacks_worker
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
    
@api_bp.route('/api/config', methods=['GET'])
@require_auth
def api_config_get():
    """Get current configuration"""
    import copy
    config = current_app.stacks_config
    config_data = copy.deepcopy(config.get_all())
    # Mask sensitive data
    if 'api' in config_data and 'key' in config_data['api']:
        config_data['api']['key'] = '***MASKED***'
    if 'login' in config_data and 'password' in config_data['login']:
        config_data['login']['password'] = '***MASKED***'
    return jsonify(config_data)