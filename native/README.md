# AtlasQuant — Native Packaging Preparation

This folder prepares native packaging metadata without claiming that signed Android/iOS packages or store publication already exist.

Current distribution remains the installable PWA.

## Rules

- Do not embed API keys, passwords, tokens or user credentials in packages.
- Do not enable real trading through packaging.
- Use the production/PWA URLs only after post-deploy health checks are green.
- Android/iOS signing credentials must stay outside the repository.
- Store publication requires separate human review and evidence.
- The metadata in `app_metadata.json` is preparation only; it is not a signed package.

## Android

Use a supported wrapper/TWA or native shell only after choosing the final store path, package id and signing account.

## iOS / iPadOS

Use a supported WebView/native shell only after confirming Apple account, bundle id, privacy disclosures and signing.

## Desktop

Windows/macOS/Linux are already covered by the PWA. Native desktop packaging remains optional and separate from the current release.
