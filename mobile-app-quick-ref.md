# 📱 WWTP Mobile App - Quick Reference Card

## 🚀 One-Line Setup

```bash
bash <(curl -s https://your-server.com/mobile-app-setup.sh)
```

---

## ⚡ Quick Commands

### Development

| Command | Description |
|---------|-------------|
| `npm start` | Start development server |
| `npm run android` | Run on Android |
| `npm run ios` | Run on iOS (Mac only) |
| `npm start -- --reset-cache` | Clear cache and start |

### Helper Scripts

| Script | Purpose |
|--------|---------|
| `./start.sh` | Start dev server |
| `./run-android.sh` | Launch on Android device/emulator |
| `./run-ios.sh` | Launch on iOS simulator (Mac) |

---

## 📊 App Structure

```
WWTPMobile/
├── App.js                 # Main app component
├── package.json           # Dependencies
├── app.json              # Expo config (if using Expo)
├── assets/               # Images, fonts
├── ios/                  # iOS native code
├── android/              # Android native code
└── node_modules/         # Dependencies
```

---

## 🔧 Configuration

### Change Backend URL

**File:** `App.js`

```javascript
// Line 19
const BACKEND_URL = 'http://192.168.1.100:5000';

// Change to your backend IP
```

### Update App Name

**Expo:** Edit `app.json`
```json
{
  "expo": {
    "name": "WWTP Monitor",
    "slug": "wwtp-mobile"
  }
}
```

**React Native:** 
- iOS: Edit `ios/WWTPMobile/Info.plist`
- Android: Edit `android/app/src/main/res/values/strings.xml`

---

## 📱 Testing

### On Real Device

**Android:**
```bash
# 1. Enable USB debugging on phone
# 2. Connect via USB
# 3. Run:
adb devices  # Verify connection
npm run android
```

**iOS (Mac only):**
```bash
# 1. Connect iPhone via USB
# 2. Trust computer on iPhone
# 3. Run:
npm run ios --device
```

### On Emulator

**Android:**
```bash
# Start Android emulator from Android Studio
# Or:
~/Library/Android/sdk/emulator/emulator -avd Pixel_5_API_33

npm run android
```

**iOS (Mac only):**
```bash
# Emulator starts automatically
npm run ios
```

---

## 🐛 Troubleshooting

### Connection Issues

```bash
# Check backend is accessible
curl http://YOUR_IP:5000/api/status

# Check WiFi connectivity
# Phone and computer must be on same network

# Check firewall
# Allow port 5000
```

### Build Errors

```bash
# Clean and rebuild
rm -rf node_modules
npm install

# Android
cd android && ./gradlew clean && cd ..

# iOS (Mac)
cd ios && pod deintegrate && pod install && cd ..
```

### Metro Bundler Issues

```bash
# Clear Metro cache
npm start -- --reset-cache

# Or
npx react-native start --reset-cache
```

---

## 📦 Building Production APK/IPA

### Android APK

```bash
cd android
./gradlew assembleRelease

# APK location:
# android/app/build/outputs/apk/release/app-release.apk
```

### Android AAB (Play Store)

```bash
cd android
./gradlew bundleRelease

# AAB location:
# android/app/build/outputs/bundle/release/app-release.aab
```

### iOS Archive (Mac only)

```bash
# 1. Open in Xcode
open ios/WWTPMobile.xcworkspace

# 2. Select "Any iOS Device"
# 3. Product → Archive
# 4. Distribute App
```

---

## 🔑 Key Features

| Feature | Status |
|---------|--------|
| Real-time data | ✅ WebSocket |
| Charts | ✅ Chart Kit |
| Parameter control | ✅ Sliders |
| Alerts | ✅ Real-time |
| Offline caching | ✅ AsyncStorage |
| Push notifications | 🔜 Coming soon |
| Dark mode | 🔜 Coming soon |

---

## 🎨 Customization

### Colors

Edit in `App.js`:

```javascript
const colors = {
  primary: '#2563eb',     // Blue
  success: '#10b981',     // Green
  warning: '#f59e0b',     // Orange
  danger: '#ef4444',      // Red
  background: '#f3f4f6',  // Light gray
};
```

### Metrics

Add new metric card in `renderOverview()`:

```javascript
<MetricCard
  label="New Metric"
  value={state.new_value}
  unit="unit"
  color="#8b5cf6"
/>
```

---

## 📊 API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | Current state |
| `/api/start` | POST | Start simulation |
| `/api/stop` | POST | Stop simulation |
| `/api/reset` | POST | Reset simulation |
| `/api/parameters` | POST | Update params |
| WebSocket | - | Real-time updates |

---

## 🔔 Notifications (Coming Soon)

```javascript
// Example implementation
import * as Notifications from 'expo-notifications';

// Send alert
await Notifications.scheduleNotificationAsync({
  content: {
    title: 'WWTP Alert',
    body: 'COD exceeds limit!',
  },
  trigger: null,
});
```

---

## 📈 Performance Tips

1. **Enable Hermes** (Android)
   - Faster startup
   - Lower memory usage
   - Already enabled in new projects

2. **Optimize Images**
   ```bash
   # Use WebP format
   # Compress images before adding
   ```

3. **Lazy Load Tabs**
   ```javascript
   // Only render active tab
   {currentTab === 'overview' && renderOverview()}
   ```

---

## 🔐 Security

### Production Checklist

- [ ] Use HTTPS for backend
- [ ] Add authentication
- [ ] Secure API tokens
- [ ] Enable SSL pinning
- [ ] Obfuscate code
- [ ] Remove debug logs

---

## 📚 Resources

- **React Native:** https://reactnative.dev
- **Expo:** https://docs.expo.dev
- **Chart Kit:** https://github.com/indiespirit/react-native-chart-kit
- **Socket.IO:** https://socket.io/docs/v4/

---

## 🆘 Quick Help

### Get Your IP Address

```bash
# Mac/Linux
ifconfig | grep "inet "
# Look for 192.168.x.x

# Windows
ipconfig
# Look for IPv4 Address
```

### Test Backend Connection

```bash
# From terminal
curl http://192.168.1.100:5000/api/status

# From phone browser
http://192.168.1.100:5000/api/status
```

### Common Errors

| Error | Solution |
|-------|----------|
| `Unable to connect` | Check IP and WiFi |
| `Network request failed` | Check backend is running |
| `Module not found` | Run `npm install` |
| `Build failed` | Clean and rebuild |

---

## 🎯 Shortcuts

### Expo

| Key | Action |
|-----|--------|
| `a` | Open Android |
| `i` | Open iOS |
| `w` | Open Web |
| `r` | Reload app |
| `m` | Toggle menu |

### Metro Bundler

| Key | Action |
|-----|--------|
| `r` | Reload |
| `d` | Open Dev Menu |

---

## 📞 Support

**Issues?** Check:
1. README.md
2. Setup guide
3. Backend logs
4. Phone console (Expo Go app)

**Still stuck?**
- Clear cache: `npm start -- --reset-cache`
- Reinstall: `rm -rf node_modules && npm install`
- Check network: Same WiFi for phone and computer

---

**Pro Tip:** Bookmark this page for quick reference!

---

*Last updated: 2026*