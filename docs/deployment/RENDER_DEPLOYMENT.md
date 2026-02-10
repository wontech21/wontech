# Render.com Deployment Guide

Complete guide to deploy WONTECH to Render.com for 24/7 cloud access.

## Prerequisites

- GitHub repository: https://github.com/wontech21/wontech
- Render.com account (free tier available)
- 10 minutes of setup time

## Step 1: Create Render Account

1. Go to: https://render.com/
2. Click "Get Started for Free"
3. Sign up with:
   - **Option A:** GitHub account (recommended - easier deployment)
   - **Option B:** Email and password
4. Verify your email

## Step 2: Connect GitHub Repository

1. Log into Render dashboard: https://dashboard.render.com/
2. Click "New +" button (top right)
3. Select "Web Service"
4. Click "Connect GitHub" (if not already connected)
5. Authorize Render to access your repositories
6. Select "wontech21/wontech" from the list
   - If you don't see it, click "Configure GitHub App" and grant access

## Step 3: Configure Web Service

Fill in the deployment form:

### Basic Settings
- **Name:** `wontech` (or your preference)
- **Region:** Choose closest to you (e.g., `Oregon (US West)`)
- **Branch:** `main`
- **Root Directory:** Leave empty
- **Runtime:** `Docker`

### Docker Settings
Render will automatically detect your Dockerfile and docker-compose.yml.

- **Dockerfile Path:** `Dockerfile` (auto-detected)
- **Docker Build Context:** `.` (auto-detected)

### Instance Type
- **Free** ($0/month) - Good for testing
  - ⚠️ Spins down after 15 min inactivity
  - ⚠️ Takes 30-60 seconds to wake up
  - ✅ Good for: Testing, low-traffic use

- **Starter** ($7/month) - Recommended for production
  - ✅ Always on, no spin-down
  - ✅ Instant response times
  - ✅ 512 MB RAM, shared CPU
  - ✅ Good for: Daily use, multiple users

### Environment Variables

Click "Add Environment Variable" and add these:

| Key | Value | Notes |
|-----|-------|-------|
| `FLASK_HOST` | `0.0.0.0` | Required - allows external connections |
| `FLASK_PORT` | `5001` | Port Flask runs on |
| `FLASK_DEBUG` | `False` | Production mode |
| `PYTHON_VERSION` | `3.11` | Ensures correct Python version |

### Advanced Settings (Optional)

- **Auto-Deploy:** `Yes` (deploys automatically when you push to GitHub)
- **Health Check Path:** `/` (Render will ping this URL to check if app is healthy)

## Step 4: Deploy

1. Click "Create Web Service" (bottom of form)
2. Render will:
   - Clone your repository
   - Build Docker image (2-3 minutes)
   - Deploy container
   - Assign a URL

3. **Monitor deployment:**
   - Watch the logs in real-time
   - Look for: "WONTECH BUSINESS MANAGEMENT PLATFORM"
   - Look for: "Dashboard starting at: http://localhost:5001"

4. **Expected deploy time:** 3-5 minutes

## Step 5: Get Your URL

After successful deployment:

1. Your app URL will be: `https://wontech-xxxx.onrender.com`
   - The `xxxx` is a random string Render assigns
   - Example: `https://wontech-abc123.onrender.com`

2. Click the URL or copy it

3. Test it in your browser:
   - Should see: "WONTECH Business Management Platform"
   - All features should work

## Step 6: Custom Domain (Optional)

### Use Your Own Domain

If you own a domain (e.g., `inventory.yourrestaurant.com`):

1. In Render dashboard → Your service → Settings
2. Scroll to "Custom Domains"
3. Click "Add Custom Domain"
4. Enter your domain: `inventory.yourrestaurant.com`
5. Follow DNS configuration instructions
6. Wait for SSL certificate (automatic, 5-10 minutes)

**Cost:** Free (Render provides SSL certificates)

## Step 7: Access from iPad

### Install as PWA (Progressive Web App)

1. **Open Safari on iPad**
2. Navigate to your Render URL: `https://wontech-xxxx.onrender.com`
3. Tap the **Share** button (square with arrow)
4. Scroll down → Tap **"Add to Home Screen"**
5. Edit name if desired → Tap **"Add"**
6. App icon appears on home screen

### Using the App

- Tap the icon → Opens full-screen (no Safari UI)
- Works like a native app
- Offline support (caches data)
- Updates automatically when online

## Troubleshooting

### Build Failed

**Error:** `failed to solve: process "/bin/sh -c pip install..."`

**Solution:**
- Check requirements.txt exists
- Verify internet connection during build
- Try: Settings → Manual Deploy → Deploy Latest Commit

### App Won't Start

**Error:** `Application failed to respond`

**Solution:**
1. Check logs for errors
2. Verify environment variables:
   - `FLASK_HOST=0.0.0.0` (must allow external connections)
   - `FLASK_PORT=5001`
3. Check Dockerfile `EXPOSE 5001` matches port

### Database Not Found

**Error:** `no such table: ingredients`

**Solution:**
- Databases are included in the Docker image
- Check that inventory.db and invoices.db exist in repository
- Verify they're not in .dockerignore

### Slow Response (Free Tier)

**Issue:** App takes 30-60 seconds to load

**Explanation:** Free tier spins down after 15 minutes of inactivity

**Solutions:**
- Upgrade to Starter ($7/month) for always-on
- OR: Accept the delay (good for testing)
- OR: Use a service like UptimeRobot to ping every 14 minutes (keeps it awake)

### Can't Access from iPad

**Issue:** URL doesn't load on iPad

**Solutions:**
1. Check iPad has internet connection
2. Verify URL is correct (copy-paste from Render dashboard)
3. Check Render service status (should be "Live" with green dot)
4. Wait 5 minutes after deployment completes
5. Try different network (cellular vs WiFi)

## Updating Your App

After making changes locally:

### Automatic Deployment (Recommended)

```bash
# Make your changes
edit dashboard.js

# Commit and push
git add .
git commit -m "Updated sales chart colors"
git push

# Render automatically:
# 1. Detects push (via GitHub webhook)
# 2. Pulls latest code
# 3. Rebuilds Docker image
# 4. Deploys new version (2-3 minutes)
```

**No manual steps needed!** Render deploys automatically when you push to GitHub.

### Manual Deployment

If you disabled auto-deploy:

1. Go to Render dashboard → Your service
2. Click "Manual Deploy" (top right)
3. Select "Deploy latest commit"
4. Wait for build and deployment

## Monitoring

### View Logs

1. Render dashboard → Your service
2. Click "Logs" tab
3. See real-time application logs
4. Filter by timeframe

### Check Metrics

1. Render dashboard → Your service
2. Click "Metrics" tab
3. See:
   - CPU usage
   - Memory usage
   - Request counts
   - Response times

### Set Up Alerts (Paid Plans)

1. Settings → Notifications
2. Add email for:
   - Deploy failures
   - Service crashes
   - High CPU/memory

## Backup Strategy

### Database Backups

**Important:** Render containers are ephemeral. Database changes are lost on redeploy!

**Solution:** Use Render Disks (Persistent Storage)

1. Render dashboard → Your service → Settings
2. Scroll to "Disks"
3. Click "Add Disk"
4. Configure:
   - **Name:** `data`
   - **Mount Path:** `/app/data`
   - **Size:** 1 GB (free tier) or more
5. Update docker-compose.yml to use `/app/data/inventory.db`

**OR:** Regular backups

```bash
# Download database periodically
curl https://wontech-xxxx.onrender.com/api/backup > backup.db
```

## Cost Breakdown

### Free Tier
- **Cost:** $0/month
- **Limitations:**
  - Spins down after 15 min inactivity
  - 750 hours/month (sufficient for 1 app)
  - Shared resources
- **Best for:** Testing, personal use, low traffic

### Starter Plan
- **Cost:** $7/month
- **Benefits:**
  - Always on (no spin-down)
  - Instant response
  - 512 MB RAM
  - Dedicated resources
- **Best for:** Production use, daily operations

### Professional Plan
- **Cost:** $25/month
- **Benefits:**
  - 2 GB RAM
  - Faster CPU
  - Priority support
- **Best for:** High traffic, multiple users

## Security Considerations

### Environment Variables

Never commit sensitive data to GitHub:
- Database passwords
- API keys
- Secret tokens

Store them in Render environment variables instead.

### HTTPS

- Render provides free SSL/TLS certificates
- All traffic encrypted automatically
- Custom domains get SSL certificates too

### Authentication (Future Enhancement)

Currently, the app has no authentication. Consider adding:
- Basic Auth for simple protection
- OAuth for enterprise use
- IP whitelist for security

## Support

### Render Support
- Free tier: Community support (https://community.render.com/)
- Paid tiers: Email support

### App Issues
- GitHub Issues: https://github.com/wontech21/wontech/issues

## Next Steps

After deployment:

1. ✅ Test all features on cloud URL
2. ✅ Install PWA on iPad
3. ✅ Test offline functionality
4. ✅ Set up automatic backups
5. ✅ Consider upgrading to Starter plan for production
6. ✅ Add custom domain (optional)
7. ✅ Set up monitoring/alerts

## Quick Reference

- **Dashboard:** https://dashboard.render.com/
- **Your Service:** https://dashboard.render.com/web/[your-service-id]
- **App URL:** https://wontech-xxxx.onrender.com
- **GitHub Repo:** https://github.com/wontech21/wontech
- **Docs:** https://render.com/docs
