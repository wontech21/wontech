# Docker Setup Guide - Phase 2 Completion

## What Was Done So Far

✅ Created `Dockerfile` - Container build instructions
✅ Created `docker-compose.yml` - Service orchestration
✅ Created `.dockerignore` - Build optimization
✅ Committed Docker files to git (commit: 1a23b96)

## What's Next: Install Docker Desktop

Docker Desktop is required to build and run containers on macOS.

### Step 1: Install Docker Desktop (5-10 minutes)

**Option A: Download from Website**
1. Go to: https://www.docker.com/products/docker-desktop
2. Click "Download for Mac"
3. Choose your Mac type:
   - **Apple Silicon (M1/M2/M3):** Download "Mac with Apple chip"
   - **Intel Mac:** Download "Mac with Intel chip"
4. Open the downloaded `.dmg` file
5. Drag Docker to Applications folder
6. Open Docker from Applications
7. Follow setup wizard (use default settings)
8. Docker icon will appear in menu bar when ready

**Option B: Install via Homebrew**
```bash
brew install --cask docker
open -a Docker
```

**Wait for Docker to start:**
- Look for Docker whale icon in menu bar
- Icon should be steady (not animated)
- This means Docker is ready

### Step 2: Verify Docker Installation

Open Terminal and run:
```bash
docker --version
docker-compose --version
```

Expected output:
```
Docker version 24.x.x, build xxxxxxx
Docker Compose version v2.x.x
```

### Step 3: Build Docker Image (2-3 minutes)

```bash
cd /Users/dell/FIRINGup
docker-compose build
```

**What this does:**
- Reads Dockerfile
- Downloads Python 3.11 base image
- Installs Flask and dependencies
- Copies your application code
- Creates container image

**Expected output:**
```
[+] Building 45.2s (12/12) FINISHED
 => [internal] load build definition from Dockerfile
 => => transferring dockerfile: 1.23kB
 => [internal] load .dockerignore
 => [1/6] FROM docker.io/library/python:3.11-slim
 => [2/6] WORKDIR /app
 => [3/6] COPY requirements.txt .
 => [4/6] RUN pip install --no-cache-dir -r requirements.txt
 => [5/6] COPY . .
 => [6/6] RUN mkdir -p /app/data
 => exporting to image
 => => naming to docker.io/library/firingup-firingup
```

### Step 4: Stop Current Flask Server

**Important:** Your regular Flask server must be stopped first (port 5001 conflict)

```bash
# Press Ctrl+C in the terminal running "python app.py"
# OR kill the process:
lsof -ti:5001 | xargs kill
```

### Step 5: Run Docker Container

```bash
docker-compose up
```

**What this does:**
- Starts container from the image
- Mounts database volumes (inventory.db, invoices.db)
- Exposes port 5001
- Runs Flask app inside container

**Expected output:**
```
[+] Running 1/1
 ✔ Container firingup-app  Created
Attaching to firingup-app
firingup-app  |
firingup-app  | ============================================================
firingup-app  | 🔥 FIRING UP INVENTORY DASHBOARD
firingup-app  | ============================================================
firingup-app  |
firingup-app  | 🔧 Checking database schema...
firingup-app  |
firingup-app  | 📊 Dashboard starting at: http://localhost:5001
firingup-app  | 📦 Inventory Database: Connected
firingup-app  | 📄 Invoices Database: Connected
firingup-app  |
firingup-app  | ⌨️  Press CTRL+C to stop the server
```

### Step 6: Test Containerized App

**Open browser:**
```
http://localhost:5001
```

**Verify:**
- ✅ Dashboard loads
- ✅ All tabs work (Inventory, Products, Sales, Invoices, Counts)
- ✅ Data is visible (from your databases)
- ✅ Can edit/add items
- ✅ Charts render correctly

**Test from another device (optional):**
1. Find your Mac's IP address:
   ```bash
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```
   Example output: `inet 192.168.1.100`

2. From iPad on same WiFi:
   - Open Safari
   - Go to: `http://192.168.1.100:5001`
   - Should see your dashboard

### Step 7: Stop Container

**Option A: Stop gracefully (keeps container)**
```bash
# Press Ctrl+C in terminal running docker-compose
```

**Option B: Stop and remove container**
```bash
docker-compose down
```

**Option C: Run in background (detached mode)**
```bash
docker-compose up -d
# View logs: docker-compose logs -f
# Stop: docker-compose down
```

## Common Commands

### Build and Run
```bash
docker-compose up          # Build and run (foreground)
docker-compose up -d       # Build and run (background)
docker-compose up --build  # Force rebuild and run
```

### Stop and Remove
```bash
docker-compose down        # Stop and remove containers
docker-compose down -v     # Also remove volumes (WARNING: deletes data)
```

### View Logs
```bash
docker-compose logs        # View all logs
docker-compose logs -f     # Follow logs (live)
docker-compose logs --tail=50  # Last 50 lines
```

### Container Management
```bash
docker ps                  # List running containers
docker ps -a               # List all containers
docker images              # List images
```

### Access Container Shell (debugging)
```bash
docker-compose exec firingup /bin/bash
# Now you're inside the container
# Can run: ls, python, sqlite3, etc.
# Exit with: exit
```

### Clean Up (if needed)
```bash
docker-compose down              # Stop containers
docker system prune -a           # Remove unused images/containers
docker volume prune              # Remove unused volumes
```

## Troubleshooting

### Port Already in Use
**Error:** `Bind for 0.0.0.0:5001 failed: port is already allocated`

**Solution:**
```bash
# Kill process using port 5001
lsof -ti:5001 | xargs kill

# Or change port in docker-compose.yml:
ports:
  - "5002:5001"  # Access at localhost:5002
```

### Database Not Found
**Error:** `no such table: ingredients`

**Solution:**
- Ensure inventory.db exists in project root
- Check volume mounting in docker-compose.yml
- Databases should be visible in container:
  ```bash
  docker-compose exec firingup ls -lh /app/*.db
  ```

### Can't Access from iPad
**Issue:** Safari times out on `http://192.168.1.100:5001`

**Solutions:**
1. Check Mac firewall:
   - System Settings → Network → Firewall → Allow incoming connections
2. Verify both devices on same WiFi
3. Verify container is running: `docker ps`
4. Check FLASK_HOST is set to 0.0.0.0 (not localhost)

### Image Build Fails
**Error:** `failed to solve: process "/bin/sh -c pip install..."`

**Solutions:**
1. Check requirements.txt exists and is correct
2. Verify internet connection (downloads packages)
3. Try rebuilding:
   ```bash
   docker-compose build --no-cache
   ```

### Container Keeps Restarting
**Check logs:**
```bash
docker-compose logs firingup
```

**Common causes:**
- Port conflict (5001 already in use)
- Database path error
- Python syntax error in code
- Missing dependencies

## Comparing Local vs Docker

### Local Development (python app.py)
```
✅ Instant code changes (auto-reload)
✅ Easier debugging
✅ Direct file access
❌ Not production-ready
❌ Mac must stay on
❌ Environment differences
```

### Docker Container (docker-compose up)
```
✅ Production-like environment
✅ Isolated dependencies
✅ Portable (runs anywhere)
✅ Ready for cloud deployment
❌ Must rebuild for code changes
❌ Extra step to access logs
```

## Phase 2 Success Criteria

When you've completed these steps, Phase 2 is done:

- [x] Docker Desktop installed
- [x] Docker image builds successfully
- [x] Container runs without errors
- [x] Dashboard accessible at localhost:5001
- [x] All features work identically to local version
- [x] (Optional) Accessible from iPad on local network

## Next: Phase 3

Once Phase 2 is verified working, you're ready for **Phase 3: Cloud Deployment**

Phase 3 will:
- Push code to GitHub
- Deploy to Render.com
- Get permanent URL (accessible anywhere)
- Enable iPad access from anywhere

---

**Current Status:** Docker files created and committed. Waiting for Docker Desktop installation to proceed with build and test.
