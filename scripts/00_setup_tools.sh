#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# 00_setup_tools.sh
# Downloads the MongoDB Database Tools (mongoimport / mongoexport) and adds
# them to PATH for the current shell session.
#
# Usage:  source scripts/00_setup_tools.sh
#         (use "source" so the PATH change survives in your current terminal)
# No "set -e" here on purpose: this file is sourced, and "set -e" would close
# your terminal on the first failing command.
# -----------------------------------------------------------------------------

TOOLS_VERSION="100.3.1"
TOOLS_DIR="mongodb-database-tools-ubuntu1804-x86_64-${TOOLS_VERSION}"

if [ ! -d "${TOOLS_DIR}" ]; then
  wget -q "https://fastdl.mongodb.org/tools/db/${TOOLS_DIR}.tgz"
  tar -xf "${TOOLS_DIR}.tgz"
fi

# Prepend (not append) so this version wins over any preinstalled copy.
# Appending ($PATH:dir) would be searched LAST, and a preinstalled
# mongoimport in /usr/bin would shadow it (lesson learned in this project).
export PATH="$(pwd)/${TOOLS_DIR}/bin:${PATH}"

# Verify instead of trusting an "echo done"
echo "mongoimport -> $(command -v mongoimport)"
mongoimport --version | head -n 1
echo "mongoexport -> $(command -v mongoexport)"
mongoexport --version | head -n 1
