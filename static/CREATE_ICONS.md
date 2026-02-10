# Create PWA Icons

Before deploying, create these icon files:

## Required Files

1. **icon-192.png** (192x192 pixels)
2. **icon-512.png** (512x512 pixels)

## Options to Create

### Option 1: Use Your Logo
- Export your WONTECH logo at 192x192 and 512x512
- Transparent background recommended
- PNG format

### Option 2: Create Simple Icon
Use an online tool like:
- https://favicon.io/
- https://www.favicon-generator.org/
- Canva

### Option 3: Use Barcode Icon
- Download free barcode scanner icon
- Resources:
  - https://www.flaticon.com/
  - https://icons8.com/
  - https://fontawesome.com/

### Option 4: Quick Placeholder (Development Only)

Create solid color icons with text:

```bash
# Install ImageMagick (if not installed)
# brew install imagemagick  # macOS
# sudo apt-get install imagemagick  # Linux

# Generate 192x192 icon
convert -size 192x192 xc:"#6f42c1" \
  -font Arial -pointsize 80 -fill white \
  -gravity center -annotate +0+0 "FU" \
  static/icon-192.png

# Generate 512x512 icon
convert -size 512x512 xc:"#6f42c1" \
  -font Arial -pointsize 200 -fill white \
  -gravity center -annotate +0+0 "FU" \
  static/icon-512.png
```

## Icon Design Tips

- **Simple**: Clear at small sizes
- **High contrast**: Visible on all backgrounds
- **Recognizable**: Unique to your brand
- **Square**: Don't rely on rounded corners (system adds them)
- **No text**: Unless very large and readable

## After Creating Icons

Place in `/Users/dell/WONTECH/static/`:
- icon-192.png
- icon-512.png

Icons are referenced in `static/manifest.json` and will be used when users install the PWA on their home screen.
