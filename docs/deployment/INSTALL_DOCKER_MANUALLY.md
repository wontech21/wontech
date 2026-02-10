# Docker Desktop Manual Installation

The automated installation needs your administrator password. Here's how to install manually:

## Option 1: Complete Homebrew Installation (Recommended - 2 minutes)

Run this command in your terminal - it will prompt for your password:

```bash
brew install --cask docker
```

**Enter your Mac password when prompted**

Then launch Docker:
```bash
open -a Docker
```

**Wait 30-60 seconds** for Docker to start. You'll see a whale icon in your menu bar.

## Option 2: Download Directly (5 minutes)

1. **Download Docker Desktop:**
   - Go to: https://www.docker.com/products/docker-desktop
   - Click "Download for Mac"
   - Choose: **Mac with Apple chip** (your Mac is Apple Silicon)

2. **Install:**
   - Open the downloaded `Docker.dmg` file
   - Drag Docker icon to Applications folder
   - Open Docker from Applications

3. **Setup:**
   - Follow the setup wizard (accept defaults)
   - You'll need to enter your password
   - Wait for Docker icon to appear in menu bar

## Verify Installation

Once Docker is running, come back to your terminal and run:

```bash
docker --version
docker-compose --version
```

You should see version numbers.

## Next: Come Back to This Conversation

Once you see the Docker versions, let me know and I'll continue with Phase 2 testing (building and running your app in Docker).

---

**Quick Reference:**
- Docker icon in menu bar = Docker is running
- No icon or animated icon = Docker is still starting (wait)
- Click icon → "Docker Desktop is running" = Ready to go
