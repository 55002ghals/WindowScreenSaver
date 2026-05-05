# Build-time flags. Modified by sync-to-prod.ps1 when generating the prod tree.
# Do NOT edit IS_PROD_BUILD manually in the dev folder ??it must stay False here.
IS_PROD_BUILD = True

# Default for logging.debug_enabled when config.json does not yet contain the key.
BUILD_DEFAULT_DEBUG_LOGGING = not IS_PROD_BUILD
