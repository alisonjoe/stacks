# Tampermonkey

The Tampermonkey extension integrates seamlessly with Anna's Archive, adding download buttons directly to search results and book detail pages.

## Installing the Tampermonkey Script

1. **Install Tampermonkey** in your browser:

   - [Chrome](https://www.tampermonkey.net/index.php?browser=chrome)
   - [Firefox](https://www.tampermonkey.net/index.php?browser=firefox)
   - [Edge](https://www.tampermonkey.net/index.php?browser=edge)
   - [Safari](https://www.tampermonkey.net/index.php?browser=safari)
   - [Opera](https://www.tampermonkey.net/index.php?browser=opera)

   If you've never used Tampermonkey before, make sure to follow the installation instructions carefully. There are a few required extra steps to get any Tampermonkey script to work.

2. **Install the Stacks script**:

   - Visit `http://localhost:7788` in your browser
   - Click the Tampermonkey link in the footer
   - Click "Install" when prompted

3. **Configure the script**:

   - Go to Anna's Archive
   - Click the Tampermonkey icon → **Stacks menu** → **⚙️ Stacks Settings**
   - Set your server URL (default: `http://localhost:7788`)
     - For network access, use your server's IP, for instance: `http://192.168.1.100:7788`
   - Enter your API key (found in Settings tab of web interface)
   - Enable/disable notifications
   - Click **Test Connection** to verify
   - Click **Save Settings**

4. **Start downloading!**
   - Browse Anna's Archive as normal
   - Click the new **Download** button next to any book
   - The book is instantly added to your Stacks queue
   - Monitor progress in the Stacks dashboard
