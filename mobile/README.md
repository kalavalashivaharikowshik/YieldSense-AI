# YieldSense AI – Mobile App

Expo (React Native) app for YieldSense AI. It talks to the FastAPI backend in
`../backend`.

## Setup

```bash
cd mobile
npm install
cp .env.example .env   # then set EXPO_PUBLIC_API_BASE_URL
npx expo start -c
```

`EXPO_PUBLIC_API_BASE_URL` must point at the API **including** the `/api`
prefix. On a phone, use your computer's LAN IP (not `localhost`), for example
`http://192.168.1.10:8000/api`.

## Checks

```bash
npx eslint .
```

## Builds

Android builds use EAS (`eas.json`):

```bash
npx eas build --platform android --profile preview   # installable APK
```

For EAS builds, set `EXPO_PUBLIC_API_BASE_URL` in the EAS environment for the
project. The app stops at startup with a clear error if it is missing.
