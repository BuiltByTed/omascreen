# Icons and artwork

Omascreen offers online Mac artwork, Lucide device icons, a custom image, the
Omascreen icon, or the exact computer icon retrieved directly from a Mac.

## Online Mac artwork

The current catalog comes from
[callumgare/macos-device-icons](https://github.com/callumgare/macos-device-icons),
which exports macOS device artwork and maps it to model identifiers. Omascreen
ships only a model-to-filename index and downloads PNG images over HTTPS from
revision `b66fbfa86b5faaeea1c7723ea49e523d5d7f10d5`. Downloads have a size limit,
are decoded/validated, and are written atomically into the user's private icon
directory. Once cached, no network request is needed to display the icon.

The catalog does not cover every recent Mac. It includes the Mac Studio enclosure
but currently lacks the 2024 Mac mini artwork. Unknown models keep the app icon;
users can import an image or fetch the exact Mac icon over SSH. Local Bonjour
`_device-info` records can provide the model without credentials or File Sharing.
VPNs and routed networks often do not carry Bonjour; enter the model identifier
manually in that case. Color-specific catalog entries can be entered as the full
identifier if known; color is not automatically inferred.

Automatic downloading contacts GitHub's image host, which receives the usual
network request metadata, including the client's public IP and requested artwork.
It does not receive Mac passwords or connection profile data. Choose **Lucide**,
**Custom image**, or **Omascreen icon**, or use `--no-fetch-icon`, to avoid automatic
artwork requests. Detection itself contacts the remote computer and local mDNS.

The catalog being public does not make Apple's artwork openly licensed.
Downloading on demand does not grant redistribution rights. This project does
not bundle Apple images, including in source history, wheels, or releases.
Apple owns its device artwork; see the source catalog and Apple's applicable
terms. Omascreen's AGPL license applies to its code, not to downloaded Apple art.

## Fetch from a Mac

macOS provides the current computer's icon through AppKit's
`NSImageNameComputer`. Omascreen can ask for this over a pre-existing trusted
SSH key/agent login, export PNG data, and save it locally. It uses strict known
host checking and never changes Mac settings. Enable **Remote Login** and verify
that `ssh mac-user@mac.local` works from the laptop first. **File Sharing is not
required.** This is optional; online downloads do not use SSH.

## Lucide and custom images

The monitor, laptop, computer, and server SVGs come from
[Lucide](https://lucide.dev/) and retain the project's
[ISC / MIT license notices](../src/screen_sharing/native/assets/LICENSE-lucide).
These four device styles ship with Omascreen for offline use.

A custom image is normalized to PNG and copied into Omascreen's private icon
directory. Supported input types depend on Qt's image readers and include PNG,
JPEG, WebP, and SVG. Input dimensions are limited to 4096 × 4096 and the stored
copy is scaled to at most 1024 × 1024. Moving the original file later does not
break the launcher. Cached/imported artwork is retained when a profile is removed.

## App icon

The original Omascreen application icon is
[`src/screen_sharing/native/assets/omascreen.png`](../src/screen_sharing/native/assets/omascreen.png).
It was created with OpenAI's built-in image-generation tool for this project;
it contains no Apple logo or copied device artwork. The original prompt used
our working name, before the app was renamed:

> Use case: logo-brand. Asset type: production desktop application icon for OmaScreenShare, a native Omarchy Linux app for connecting to Mac desktops. Primary request: create a distinctive, polished app icon based on two overlapping display windows linked into one coherent symbol, suggesting a remote screen being brought onto your desktop. Style: simple geometric silhouette with restrained dimensional depth and crisp substantial edges, professional Linux desktop icon, readable at 32px and beautiful at 512px. Composition: one centered square icon composition, generous safe margins, no surrounding mockup, actual transparent background outside the icon. Constraints: no text, no letters, no Apple logo, no Linux mascot, no watermark, no tiny details, no busy scene. The result should feel like a purposeful desktop tool, not generic cloud clip art.
