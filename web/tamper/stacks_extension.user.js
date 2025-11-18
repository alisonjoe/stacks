// ==UserScript==
// @name         Stacks - Anna's Archive Downloader
// @namespace    http://tampermonkey.net/
// @version      1.0.1
// @description  Add download buttons to Anna's Archive that queue downloads to Stacks server
// @author       Zelest Carlyone
// @match        https://annas-archive.org/*
// @icon         https://annas-archive.org/favicon.ico
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @connect      localhost
// @connect      127.0.0.1
// @connect      *
// ==/UserScript==

(function() {
    'use strict';

    // ============================================================
    // 🔧 CONFIGURATION - CHANGE YOUR SERVER URL HERE
    // ============================================================
    
    const DEFAULT_SERVER_URL = 'http://localhost:7788';
    
    // ============================================================
    // Advanced Configuration (usually don't need to change)
    // ============================================================
    
    const CONFIG = {
        serverUrl: GM_getValue('stacksServerUrl', DEFAULT_SERVER_URL),
        apiKey: GM_getValue('stacksApiKey', ''),
        showNotifications: GM_getValue('stacksShowNotifications', true)
    };
    
    // Add settings menu command
    GM_registerMenuCommand('⚙️ Stacks Settings', showSettingsDialog);
    GM_registerMenuCommand('🔄 Reset to Default Server', resetToDefault);

    // Settings dialog
    function showSettingsDialog() {
        const currentUrl = GM_getValue('stacksServerUrl', DEFAULT_SERVER_URL);
        const currentApiKey = GM_getValue('stacksApiKey', '');
        const currentNotifications = GM_getValue('stacksShowNotifications', true);
        
        const dialog = document.createElement('div');
        dialog.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            z-index: 10001;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 500px;
            width: 90%;
        `;
        
        dialog.innerHTML = `
            <h2 style="margin: 0 0 20px 0; color: #333;">⚙️ Stacks Settings</h2>
            
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #555;">
                    Server URL:
                </label>
                <input type="text" id="stacksServerUrl" value="${currentUrl}" 
                       style="width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 4px; font-size: 14px; font-family: monospace;"
                       placeholder="http://your-server:7788">
                <div style="margin-top: 8px; font-size: 12px; color: #666;">
                    Examples:<br>
                    • Local: <code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">http://localhost:7788</code><br>
                    • Network: <code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">http://192.168.1.100:7788</code><br>
                    • Remote: <code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">http://yourdomain.com:7788</code>
                </div>
            </div>
            
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #555;">
                    API Key:
                </label>
                <input type="password" id="stacksApiKey" value="${currentApiKey}" 
                       style="width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 4px; font-size: 14px; font-family: monospace;"
                       placeholder="Your 32-character API key">
                <div style="margin-top: 8px; font-size: 12px; color: #666;">
                    <strong>📍 Find your API key:</strong> Open Stacks web interface → Settings tab → API Key section (click Copy button).
                </div>
            </div>
            
            <div style="margin-bottom: 25px;">
                <label style="display: flex; align-items: center; cursor: pointer;">
                    <input type="checkbox" id="stacksShowNotifications" ${currentNotifications ? 'checked' : ''}
                           style="margin-right: 8px; width: 18px; height: 18px; cursor: pointer;">
                    <span style="color: #555; font-weight: 600;">Show notifications</span>
                </label>
            </div>
            
            <div style="margin-bottom: 20px; padding: 15px; background: #f0f8ff; border-left: 4px solid #2196F3; border-radius: 4px;">
                <div style="font-weight: 600; color: #1976D2; margin-bottom: 5px;">💡 Connection Test</div>
                <div id="connectionStatus" style="font-size: 13px; color: #666;">
                    Click "Test Connection" to verify
                </div>
                <button id="testConnection" style="margin-top: 10px; padding: 6px 12px; background: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;">
                    Test Connection
                </button>
            </div>
            
            <div style="display: flex; gap: 10px; justify-content: flex-end;">
                <button id="cancelSettings" style="padding: 10px 20px; background: #757575; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">
                    Cancel
                </button>
                <button id="saveSettings" style="padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">
                    Save Settings
                </button>
            </div>
        `;
        
        // Overlay
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 10000;
        `;
        
        document.body.appendChild(overlay);
        document.body.appendChild(dialog);
        
        // Test connection
        dialog.querySelector('#testConnection').addEventListener('click', async () => {
            const testUrl = dialog.querySelector('#stacksServerUrl').value;
            const testApiKey = dialog.querySelector('#stacksApiKey').value;
            const statusDiv = dialog.querySelector('#connectionStatus');
            const testBtn = dialog.querySelector('#testConnection');
            
            if (!testApiKey) {
                statusDiv.innerHTML = `❌ <strong>API key required</strong><br>Get it from Stacks web interface → Settings`;
                statusDiv.style.color = '#f44336';
                return;
            }
            
            testBtn.disabled = true;
            testBtn.textContent = 'Testing...';
            statusDiv.textContent = 'Connecting...';
            statusDiv.style.color = '#666';
            
            GM_xmlhttpRequest({
                method: 'GET',
                url: `${testUrl}/api/status`,
                headers: {
                    'X-API-Key': testApiKey
                },
                timeout: 7788,
                onload: (response) => {
                    try {
                        if (response.status === 401 || response.status === 403) {
                            statusDiv.innerHTML = `❌ <strong>Invalid API key</strong><br>Check your API key in web interface → Settings`;
                            statusDiv.style.color = '#f44336';
                        } else if (response.status === 200) {
                            const data = JSON.parse(response.responseText);
                            statusDiv.innerHTML = `✅ <strong>Connected!</strong><br>Queue: ${data.queue_size}, History: ${data.recent_history.length} items`;
                            statusDiv.style.color = '#4CAF50';
                        } else {
                            statusDiv.innerHTML = `❌ <strong>Error ${response.status}</strong><br>${response.statusText}`;
                            statusDiv.style.color = '#f44336';
                        }
                    } catch (e) {
                        statusDiv.innerHTML = `❌ <strong>Invalid response</strong><br>Server returned non-JSON data`;
                        statusDiv.style.color = '#f44336';
                    }
                    testBtn.disabled = false;
                    testBtn.textContent = 'Test Connection';
                },
                onerror: (error) => {
                    statusDiv.innerHTML = `❌ <strong>Connection failed</strong><br>Could not reach server at ${testUrl}`;
                    statusDiv.style.color = '#f44336';
                    testBtn.disabled = false;
                    testBtn.textContent = 'Test Connection';
                },
                ontimeout: () => {
                    statusDiv.innerHTML = `❌ <strong>Connection timeout</strong><br>Server took too long to respond`;
                    statusDiv.style.color = '#f44336';
                    testBtn.disabled = false;
                    testBtn.textContent = 'Test Connection';
                }
            });
        });
        
        // Save
        dialog.querySelector('#saveSettings').addEventListener('click', () => {
            const newUrl = dialog.querySelector('#stacksServerUrl').value.trim();
            const newApiKey = dialog.querySelector('#stacksApiKey').value.trim();
            const newNotifications = dialog.querySelector('#stacksShowNotifications').checked;
            
            if (!newUrl) {
                alert('Please enter a server URL');
                return;
            }
            
            if (!newApiKey) {
                alert('Please enter an API key\n\nGet it from: Stacks web interface → Settings tab → API Key section');
                return;
            }
            
            GM_setValue('stacksServerUrl', newUrl);
            GM_setValue('stacksApiKey', newApiKey);
            GM_setValue('stacksShowNotifications', newNotifications);
            
            CONFIG.serverUrl = newUrl;
            CONFIG.apiKey = newApiKey;
            CONFIG.showNotifications = newNotifications;
            
            overlay.remove();
            dialog.remove();
            
            showNotification('✓ Settings saved! Refresh the page to apply changes.', 'success');
        });
        
        // Cancel
        const closeDialog = () => {
            overlay.remove();
            dialog.remove();
        };
        
        dialog.querySelector('#cancelSettings').addEventListener('click', closeDialog);
        overlay.addEventListener('click', closeDialog);
    }
    
    // Reset to default
    function resetToDefault() {
        if (confirm(`Reset server URL to:\n${DEFAULT_SERVER_URL}\n\nYou'll need to re-enter your API key.`)) {
            GM_setValue('stacksServerUrl', DEFAULT_SERVER_URL);
            GM_setValue('stacksApiKey', '');
            GM_setValue('stacksShowNotifications', true);
            CONFIG.serverUrl = DEFAULT_SERVER_URL;
            CONFIG.apiKey = '';
            CONFIG.showNotifications = true;
            alert('Settings reset! Please configure your API key in settings.');
        }
    }

    // Utility: Extract MD5 from URL or href
    function extractMD5(url) {
        const match = url.match(/\/md5\/([a-f0-9]{32})/);
        return match ? match[1] : null;
    }

    // Utility: Show notification
    function showNotification(message, type = 'info') {
        if (!CONFIG.showNotifications) return;

        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
            color: white;
            border-radius: 4px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            z-index: 10000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            max-width: 300px;
            animation: slideIn 0.3s ease-out;
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Add CSS animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(400px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(400px); opacity: 0; }
        }
        .stacks-btn {
            transition: opacity 0.2s, transform 0.1s;
        }
        .stacks-btn:hover {
            opacity: 0.8;
            transform: scale(1.05);
        }
        .stacks-btn:active {
            transform: scale(0.95);
        }
    `;
    document.head.appendChild(style);

    // API: Add to queue
    function addToQueue(md5, title = 'Unknown', source = 'browser') {
        if (!CONFIG.apiKey) {
            return Promise.reject(new Error('⚠️ API key not configured.\n\nGet your API key from:\nStacks web interface → Settings tab → API Key section\n\nThen configure it here:\nTampermonkey icon → Stacks Settings'));
        }
        
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'POST',
                url: `${CONFIG.serverUrl}/api/queue/add`,
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': CONFIG.apiKey
                },
                data: JSON.stringify({
                    md5: md5,
                    title: title,
                    source: source
                }),
                onload: (response) => {
                    try {
                        if (response.status === 401 || response.status === 403) {
                            reject(new Error('Invalid API key. Get a new key from web interface → Settings.'));
                            return;
                        }
                        const data = JSON.parse(response.responseText);
                        resolve(data);
                    } catch (e) {
                        reject(new Error('Failed to parse response'));
                    }
                },
                onerror: (error) => {
                    reject(new Error('Failed to connect to Stacks server'));
                },
                ontimeout: () => {
                    reject(new Error('Request timed out'));
                }
            });
        });
    }

    // Create download button
    function createDownloadButton(md5, title) {
        const btn = document.createElement('a');
        btn.href = '#';
        btn.className = 'custom-a text-[#2563eb] inline-block outline-offset-[-2px] outline-2 rounded-[3px] focus:outline font-semibold text-sm leading-none hover:opacity-80 relative stacks-btn';
        btn.innerHTML = '<span class="text-[15px] align-text-bottom inline-block icon-[typcn--download] mr-[1px]"></span>Download';
        btn.title = `Add to Stacks queue: ${title}`;

        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();

            // Visual feedback
            const originalText = btn.innerHTML;
            btn.innerHTML = '<span class="text-[15px] align-text-bottom inline-block icon-[svg-spinners--ring-resize] mr-[1px]"></span>Adding...';
            btn.style.pointerEvents = 'none';

            try {
                const result = await addToQueue(md5, title, 'search-page');

                if (result.success) {
                    showNotification(`✓ Added to queue: ${title}`, 'success');
                    btn.innerHTML = '<span class="text-[15px] align-text-bottom inline-block icon-[mdi--check] mr-[1px]"></span>Queued';
                    setTimeout(() => {
                        btn.innerHTML = originalText;
                        btn.style.pointerEvents = 'auto';
                    }, 2000);
                } else {
                    showNotification(`Already in queue: ${title}`, 'info');
                    btn.innerHTML = originalText;
                    btn.style.pointerEvents = 'auto';
                }
            } catch (error) {
                showNotification(`✗ ${error.message}`, 'error');
                btn.innerHTML = originalText;
                btn.style.pointerEvents = 'auto';
            }
        });

        return btn;
    }

    // Add button to search results
    function addButtonsToSearchResults() {
        // Find all search result items
        const items = document.querySelectorAll('.flex.pt-3.pb-3.border-b');

        items.forEach(item => {
            // Skip if already processed
            if (item.dataset.stacksProcessed) return;
            item.dataset.stacksProcessed = 'true';

            // Extract MD5 from the main link
            const mainLink = item.querySelector('a.js-vim-focus.custom-a');
            if (!mainLink) return;

            const md5 = extractMD5(mainLink.href);
            if (!md5) return;

            // Extract title
            const title = mainLink.textContent.trim() || 'Unknown';

            // Find the "Save" button
            const saveButton = Array.from(item.querySelectorAll('a[href="#"]')).find(a => {
                return a.innerHTML.includes('bookmark') && a.textContent.includes('Save');
            });
            
            if (!saveButton) return;

            // Create and insert download button
            const downloadBtn = createDownloadButton(md5, title);
            
            // Find the parent container with metadata
            const metadataContainer = saveButton.closest('.text-gray-800');
            if (!metadataContainer) return;
            
            // Insert after the Save button
            const separator = document.createTextNode(' · ');
            saveButton.parentNode.insertBefore(separator, saveButton.nextSibling);
            saveButton.parentNode.insertBefore(downloadBtn, separator.nextSibling);
        });
    }

    // Add button to detail page
    function addButtonToDetailPage() {
        // Check if we're on an MD5 detail page
        const md5 = extractMD5(window.location.href);
        if (!md5) return;

        // Skip if already processed
        if (document.body.dataset.stacksProcessed) return;
        document.body.dataset.stacksProcessed = 'true';

        // Find the title
        const titleElement = document.querySelector('h1');
        const title = titleElement ? titleElement.textContent.trim() : 'Unknown';

        // Find the Save button
        const saveButton = Array.from(document.querySelectorAll('a[href="#"]')).find(a => {
            return a.innerHTML.includes('bookmark') && a.textContent.includes('Save');
        });

        if (!saveButton) return;

        // Create and insert download button
        const downloadBtn = createDownloadButton(md5, title);
        
        // Add separator and button after Save
        const separator = document.createTextNode(' · ');
        saveButton.parentNode.insertBefore(separator, saveButton.nextSibling);
        saveButton.parentNode.insertBefore(downloadBtn, separator.nextSibling);
    }

    // Initialize
    function init() {
        // Check if API key is configured
        if (!CONFIG.apiKey) {
            console.warn('%c⚠️ Stacks: API key not configured!', 'font-size: 14px; color: #ff9800; font-weight: bold;');
            console.warn('%c📍 Get your API key: Open Stacks web interface → Settings tab → API Key section', 'color: #ff9800;');
            console.warn('%c⚙️  Configure it here: Click Tampermonkey icon → Stacks Settings', 'color: #ff9800;');
            return;
        }
        
        const currentPath = window.location.pathname;

        if (currentPath.startsWith('/search')) {
            // Search results page
            addButtonsToSearchResults();

            // Watch for dynamic content (infinite scroll, etc.)
            const observer = new MutationObserver(() => {
                addButtonsToSearchResults();
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        } else if (currentPath.startsWith('/md5/')) {
            // Detail page
            addButtonToDetailPage();
        }
    }

    // Run when page is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Startup logs
    console.log('%c📚 Stacks Extension Loaded', 'font-size: 14px; font-weight: bold; color: #4CAF50;');
    console.log('%cServer: ' + CONFIG.serverUrl, 'color: #2196F3;');
    
    if (CONFIG.apiKey) {
        console.log('%c✓ API Key: Configured', 'color: #4CAF50;');
    } else {
        console.log('%c✗ API Key: NOT CONFIGURED', 'color: #f44336; font-weight: bold;');
        console.log('%c→ Get key from: Stacks web interface → Settings tab', 'color: #ff9800;');
    }
    
    console.log('%cNotifications: ' + (CONFIG.showNotifications ? 'Enabled' : 'Disabled'), 'color: #666;');
    
    if (!CONFIG.serverUrl.includes('localhost') && !CONFIG.serverUrl.includes('127.0.0.1')) {
        console.log('%c🌐 Remote server connection', 'font-size: 12px; color: #ff9800;');
    }
})();
