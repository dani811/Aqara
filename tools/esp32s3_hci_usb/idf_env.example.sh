# Copy to idf_env.sh (git-ignored) and point the two paths at your ESP-IDF 5.3.x
# checkout and tools dir. Then: source ./idf_env.sh && idf.py set-target esp32s3 && idf.py build
export IDF_PATH="$HOME/esp/esp-idf"            # ESP-IDF v5.3.x checkout
export IDF_TOOLS_PATH="$HOME/.espressif"       # where install.sh put the toolchains
export PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONNOUSERSITE=1
source "$IDF_PATH/export.sh" >/dev/null
