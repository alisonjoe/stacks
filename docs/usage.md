# Usage

## Web Interface

The web interface provides two main tabs:

- **Downloads Tab**: Monitor current download, view queue, and check history
- **Settings Tab**: Configure download behavior, login credentials, fast download API, and logging

The dashboard updates in real-time every 2 seconds, showing:

- Current download progress with live percentage and transfer rate
- Queue size and upcoming downloads
- Recent download history with success/failure indicators
- Fast download quota (when enabled)

## Getting a Fast Download Key

1. Become a member of Anna's Archive (supports the project!)
2. Log into your account on Anna's Archive
3. Navigate to your account settings
4. Find your secret key in the API/Fast Downloads section
5. Copy the key and paste it into the Settings tab in Stacks
6. Click "Test Key" to verify it works
7. Enable fast downloads and save settings

The dashboard will show your remaining fast downloads quota when enabled.

## Authentication

### Default Credentials

- **Default username:** `admin`
- **Default password:** `stacks`

**IMPORTANT:** Change the default password after first login via the Settings tab!

### Changing Login Credentials

You can change your login credentials in two ways:

1. **Via Web Interface**

   - Log in to Stacks
   - Go to Settings tab
   - Update Username and/or Password
   - Click Save Settings

2. **Via Environment Variables**

   This sets the initial credentials only. Once set, you must change credentials via web interface or reset the password through the methods mentioned below.

   Edit `docker-compose.yml`:

   ```yaml
   environment:
     - USERNAME=yourusername
     - PASSWORD=yourpassword
   ```

### Resetting Forgotten Password

If you forget your password:

1. Stop the container
2. Edit `docker-compose.yml` and set:
   ```yaml
   environment:
     - RESET_ADMIN=true
     - PASSWORD=new_password
   ```
3. Restart the container with `docker compose up` or `./build.sh`
4. Log in with the new password
5. Remove `RESET_ADMIN=true` from docker-compose.yml