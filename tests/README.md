# Tests

This directory contains lightweight sanity checks for the open-source package.

The tests use mock values such as `test-key`, `ak-test`, and `sk-test`. They are not real credentials.

Run the repository health check:

```bash
python tests/test_repository_health.py
```

Run individual node checks when optional dependencies are available:

```bash
python tests/test_aliyun_translate.py
python tests/test_gemini_image_retry.py
python tests/test_skill_router.py
```
