#!/bin/bash
# build-tarball.sh - portable tar.gz with all Python deps bundled.
# A portable archive must vendor its deps (like the AppImage); the distro
# packages (.deb/AUR) are the ones that use system PyQt6 instead.
set -euo pipefail

cd "$(dirname "$0")/../.."

VERSION=$(python3 -c "exec(open('easy_scsmodmanager/__init__.py').read()); print(__version__)")
APP_ID="io.github.switch_bros.EasySCSModManager"
DIST_NAME="EasySCSModManager-${VERSION}-linux-x86_64"
DIST_DIR="dist/${DIST_NAME}"

echo "Building tar.gz for Easy SCSModManager v${VERSION}..."

rm -rf "${DIST_DIR}" "dist/${DIST_NAME}.tar.gz"
mkdir -p "${DIST_DIR}"/{bin,lib,share/{applications,icons/hicolor/scalable/apps,metainfo}}

# Build wheel and install it + its deps into lib/
python3 -m build --wheel --no-isolation
pip install --target="${DIST_DIR}/lib" dist/easy_scsmodmanager-*.whl

# Launcher
cat > "${DIST_DIR}/bin/easy-scsmodmanager" << 'LAUNCHER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${SCRIPT_DIR}/lib:${PYTHONPATH:-}"
exec python3 -m easy_scsmodmanager "$@"
LAUNCHER
chmod +x "${DIST_DIR}/bin/easy-scsmodmanager"

# Desktop integration
cp easy_scsmodmanager/resources/${APP_ID}.desktop "${DIST_DIR}/share/applications/"
cp easy_scsmodmanager/resources/icon.svg \
    "${DIST_DIR}/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
cp easy_scsmodmanager/resources/${APP_ID}.metainfo.xml "${DIST_DIR}/share/metainfo/"
cp LICENSE "${DIST_DIR}/"

# Installer to ~/.local/
cat > "${DIST_DIR}/install.sh" << 'INSTALL'
#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${HOME}/.local"
echo "Installing Easy SCSModManager to ${PREFIX}..."
mkdir -p "${PREFIX}/lib/easy-scsmodmanager"
cp -r "${SCRIPT_DIR}/lib/"* "${PREFIX}/lib/easy-scsmodmanager/"
mkdir -p "${PREFIX}/bin"
cat > "${PREFIX}/bin/easy-scsmodmanager" << EOF
#!/bin/bash
export PYTHONPATH="${PREFIX}/lib/easy-scsmodmanager:\${PYTHONPATH:-}"
exec python3 -m easy_scsmodmanager "\$@"
EOF
chmod +x "${PREFIX}/bin/easy-scsmodmanager"
mkdir -p "${PREFIX}/share/applications" "${PREFIX}/share/icons/hicolor/scalable/apps" "${PREFIX}/share/metainfo"
cp "${SCRIPT_DIR}/share/applications/"*.desktop "${PREFIX}/share/applications/"
cp "${SCRIPT_DIR}/share/icons/hicolor/scalable/apps/"*.svg "${PREFIX}/share/icons/hicolor/scalable/apps/"
cp "${SCRIPT_DIR}/share/metainfo/"*.xml "${PREFIX}/share/metainfo/"
gtk-update-icon-cache -f -t "${PREFIX}/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "${PREFIX}/share/applications" 2>/dev/null || true
echo "Done! Run with: easy-scsmodmanager"
INSTALL
chmod +x "${DIST_DIR}/install.sh"

cat > "${DIST_DIR}/README.txt" << 'README'
Easy SCSModManager - Portable Linux Distribution

QUICK START:   ./bin/easy-scsmodmanager
INSTALL:       ./install.sh   (installs to ~/.local/)
REQUIREMENTS:  Python 3.13+ with system Qt6 libraries. Python deps are bundled.
UNINSTALL:     rm -rf ~/.local/lib/easy-scsmodmanager ~/.local/bin/easy-scsmodmanager
README

cd dist
tar czf "${DIST_NAME}.tar.gz" "${DIST_NAME}"
cd ..
echo "Created: dist/${DIST_NAME}.tar.gz"
