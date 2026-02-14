#!/bin/bash
# WWTP Mobile App - Automated Setup Script
# Supports both Expo and React Native CLI approaches

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         WWTP Mobile App - Automated Setup                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
APP_NAME="WWTPMobile"
EXPO_APP_NAME="wwtp-mobile"

# Detect OS
OS_TYPE="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    OS_TYPE="windows"
fi

echo -e "${BLUE}Detected OS: $OS_TYPE${NC}"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found${NC}"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${YELLOW}⚠️  Node.js version is $NODE_VERSION, recommended 18+${NC}"
fi
echo -e "${GREEN}✓ Node.js $(node -v)${NC}"

# Check npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ npm $(npm -v)${NC}"

# Ask user which approach to use
echo ""
echo "Which setup would you like to use?"
echo "1) Expo (Recommended for beginners - easier, faster)"
echo "2) React Native CLI (Full control, better for production)"
echo ""
read -p "Enter choice [1]: " CHOICE
CHOICE=${CHOICE:-1}

if [ "$CHOICE" == "1" ]; then
    SETUP_TYPE="expo"
    PROJECT_NAME="$EXPO_APP_NAME"
else
    SETUP_TYPE="react-native"
    PROJECT_NAME="$APP_NAME"
fi

echo -e "${BLUE}Using: $SETUP_TYPE${NC}"
echo ""

# Get backend IP
echo "📡 Backend Configuration"
echo "========================"
echo ""
echo "Enter your backend server IP address"
echo "(Find it with 'ifconfig' on Mac/Linux or 'ipconfig' on Windows)"
echo "Example: 192.168.1.100"
echo ""
read -p "Backend IP [$
192.168.1.100]: " BACKEND_IP
BACKEND_IP=${BACKEND_IP:-192.168.1.100}

read -p "Backend Port [5000]: " BACKEND_PORT
BACKEND_PORT=${BACKEND_PORT:-5000}

BACKEND_URL="http://$BACKEND_IP:$BACKEND_PORT"

echo ""
echo -e "${GREEN}Backend URL: $BACKEND_URL${NC}"
echo ""

# Create project
if [ "$SETUP_TYPE" == "expo" ]; then
    echo "🚀 Creating Expo project..."
    
    # Check if expo-cli is installed
    if ! command -v expo &> /dev/null; then
        echo "Installing Expo CLI globally..."
        npm install -g expo-cli
    fi
    
    # Create Expo app
    npx create-expo-app $PROJECT_NAME --template blank
    cd $PROJECT_NAME
    
    echo -e "${GREEN}✓ Expo project created${NC}"
    
else
    echo "🚀 Creating React Native project..."
    
    # Create React Native app
    npx react-native init $APP_NAME
    cd $APP_NAME
    
    echo -e "${GREEN}✓ React Native project created${NC}"
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."

if [ "$SETUP_TYPE" == "expo" ]; then
    npm install socket.io-client@4.6.0
    npm install react-native-chart-kit@6.12.0
    npm install react-native-svg@13.9.0
    npm install @react-native-async-storage/async-storage@1.18.2
    npx expo install expo-notifications
else
    npm install socket.io-client@4.6.0
    npm install react-native-chart-kit@6.12.0
    npm install react-native-svg@13.4.0
    npm install @react-native-async-storage/async-storage@1.18.2
    npm install react-native-push-notification@8.1.1
    
    if [ "$OS_TYPE" == "macos" ]; then
        echo "Installing iOS dependencies..."
        cd ios
        pod install
        cd ..
    fi
fi

echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create App.js with configured backend URL
echo ""
echo "📝 Creating App.js..."

cat > App.js << 'APPJS_PLACEHOLDER'
APPJS_CONTENT_GOES_HERE
APPJS_PLACEHOLDER

# Replace placeholder with actual backend URL
sed -i.bak "s|http://192.168.1.100:5000|$BACKEND_URL|g" App.js
rm App.js.bak

echo -e "${GREEN}✓ App.js created and configured${NC}"

# Create package.json scripts
if [ "$SETUP_TYPE" == "expo" ]; then
    cat > package.json.tmp << EOF
{
  "name": "$PROJECT_NAME",
  "version": "1.0.0",
  "main": "node_modules/expo/AppEntry.js",
  "scripts": {
    "start": "expo start",
    "android": "expo start --android",
    "ios": "expo start --ios",
    "web": "expo start --web",
    "clear": "expo start -c"
  }
}
EOF
    # Merge with existing package.json
    node -e "
    const fs = require('fs');
    const existing = JSON.parse(fs.readFileSync('package.json', 'utf8'));
    const newScripts = JSON.parse(fs.readFileSync('package.json.tmp', 'utf8')).scripts;
    existing.scripts = {...existing.scripts, ...newScripts};
    fs.writeFileSync('package.json', JSON.stringify(existing, null, 2));
    "
    rm package.json.tmp
fi

# Create helper scripts
echo ""
echo "🔧 Creating helper scripts..."

cat > start.sh << 'START_SCRIPT'
#!/bin/bash
if command -v expo &> /dev/null; then
    npx expo start
else
    npx react-native start
fi
START_SCRIPT
chmod +x start.sh

cat > run-android.sh << 'ANDROID_SCRIPT'
#!/bin/bash
if command -v expo &> /dev/null; then
    npx expo start --android
else
    npx react-native run-android
fi
ANDROID_SCRIPT
chmod +x run-android.sh

if [ "$OS_TYPE" == "macos" ]; then
    cat > run-ios.sh << 'IOS_SCRIPT'
#!/bin/bash
if command -v expo &> /dev/null; then
    npx expo start --ios
else
    npx react-native run-ios
fi
IOS_SCRIPT
    chmod +x run-ios.sh
fi

echo -e "${GREEN}✓ Helper scripts created${NC}"

# Create README
cat > README.md << EOF
# WWTP Mobile App

Mobile application for monitoring and controlling wastewater treatment plants.

## Backend Configuration

- Backend URL: $BACKEND_URL
- Make sure your backend server is running and accessible

## Quick Start

### Start Development Server
\`\`\`bash
./start.sh
# Or: npm start
\`\`\`

### Run on Android
\`\`\`bash
./run-android.sh
# Or: npm run android
\`\`\`

### Run on iOS (Mac only)
\`\`\`bash
./run-ios.sh
# Or: npm run ios
\`\`\`

## Setup

1. Make sure backend is running on $BACKEND_URL
2. Ensure phone and computer are on same WiFi network
3. Install Expo Go app on your phone (if using Expo)
4. Scan QR code from terminal

## Troubleshooting

### Can't connect to backend
1. Check if backend is running: curl $BACKEND_URL/api/status
2. Verify IP address is correct
3. Check firewall settings
4. Ensure same WiFi network

### App crashes
\`\`\`bash
# Clear cache
npm start -- --reset-cache

# Reinstall dependencies
rm -rf node_modules
npm install
\`\`\`

## Building for Production

### Android APK
\`\`\`bash
cd android
./gradlew assembleRelease
# APK: android/app/build/outputs/apk/release/app-release.apk
\`\`\`

### iOS (Mac only)
\`\`\`bash
# Open in Xcode
open ios/$APP_NAME.xcworkspace
# Archive and distribute
\`\`\`

## Configuration

Backend URL can be changed in \`App.js\`:
\`\`\`javascript
const BACKEND_URL = '$BACKEND_URL';
\`\`\`
EOF

# Create .gitignore
cat > .gitignore << 'GITIGNORE'
# Dependencies
node_modules/

# Expo
.expo/
.expo-shared/
dist/

# Native
*.jks
*.p8
*.p12
*.key
*.mobileprovision
*.orig.*

# Metro
.metro-health-check*

# Debug
npm-debug.*
yarn-debug.*
yarn-error.*

# macOS
.DS_Store

# Temporary files
*.swp
*.swo
*~.nib

# iOS
ios/Pods/
ios/build/

# Android
android/app/build/
android/build/

# Environment
.env
GITIGNORE

# Final instructions
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  ✅ SETUP COMPLETE!                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📁 Project created in: $(pwd)"
echo "🌐 Backend URL: $BACKEND_URL"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1️⃣  Make sure your backend is running:"
echo "   cd /path/to/wwtp-dashboard"
echo "   ./start.sh"
echo ""
echo "2️⃣  Start the mobile app:"
echo "   ./start.sh"
echo ""
echo "3️⃣  On your phone:"
if [ "$SETUP_TYPE" == "expo" ]; then
    echo "   - Install 'Expo Go' from App Store/Play Store"
    echo "   - Scan the QR code shown in terminal"
else
    echo "   - Connect via USB or use emulator"
    echo "   - Run: ./run-android.sh (or run-ios.sh on Mac)"
fi
echo ""
echo "🔧 Helper Commands:"
echo "   ./start.sh          - Start development server"
echo "   ./run-android.sh    - Run on Android"
if [ "$OS_TYPE" == "macos" ]; then
    echo "   ./run-ios.sh        - Run on iOS"
fi
echo ""
echo "📚 Documentation:"
echo "   README.md           - Project documentation"
echo "   App.js              - Main application code"
echo ""
echo "🐛 Troubleshooting:"
echo "   If you can't connect:"
echo "   1. Check backend is running: curl $BACKEND_URL/api/status"
echo "   2. Verify both devices on same WiFi"
echo "   3. Check firewall allows port $BACKEND_PORT"
echo ""
echo "🎉 Happy mobile development!"
echo ""

# Offer to start immediately
read -p "Would you like to start the development server now? (y/n): " START_NOW
if [ "$START_NOW" == "y" ] || [ "$START_NOW" == "Y" ]; then
    echo ""
    echo "🚀 Starting development server..."
    ./start.sh
fi