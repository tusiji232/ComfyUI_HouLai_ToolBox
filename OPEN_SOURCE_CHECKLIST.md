# Open Source Checklist

This repository copy was prepared for public release.

## Sanitized

- Python bytecode caches were not copied.
- Local workflow outputs, logs, SQLite databases, and environment files are ignored.
- Local Windows absolute paths were replaced with user-relative example paths.
- Private/proxy API defaults were replaced with official or placeholder endpoints.
- The unrelated internal File Manager maintenance skill file was removed.
- `LICENSE` was populated with the MIT license text.

## Before Publishing

- Review screenshots and example workflows before adding them.
- Do not commit `.env`, API keys, real workflows containing tokens, customer data, or generated outputs.
- If you add demo workflows, use placeholder keys such as `YOUR_API_KEY_HERE`.
- Update README repository links after the GitHub repository name is finalized.

## Configuration Notes

Several nodes call third-party or user-provided API services. Users must provide their own API keys and endpoint URLs inside ComfyUI node inputs.
