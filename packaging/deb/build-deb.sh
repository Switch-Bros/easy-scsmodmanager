#!/bin/bash
# build-deb.sh - build a .deb for Debian/Ubuntu/SteamOS.
# Uses the distro's PyQt6 (python3-pyqt6) instead of a bundled wheel; only the
# dep that Debian does not package (vdf) is vendored in.
set -euo pipefail

cd "$(dirname "$0")/../.."

VERSION=$(python3 -c "exec(open('easy_scsmodmanager/__init__.py').read()); print(__version__)")
APP_ID="io.github.switch_bros.EasySCSModManager"
PKG_NAME="easy-scsmodmanager"
PKG_DIR="dist/deb-build/${PKG_NAME}_${VERSION}_all"

echo "Building .deb for Easy SCSModManager v${VERSION}..."

rm -rf "dist/deb-build" "dist/${PKG_NAME}_${VERSION}_all.deb"
mkdir -p "${PKG_DIR}"

# Build wheel + install the application into the package tree
python3 -m build --wheel --no-isolation
python3 -m installer --destdir="${PKG_DIR}" dist/easy_scsmodmanager-*.whl

# Vendor only the deps Debian does not package (vdf has no further deps)
SITE_PKG=$(python3 -c "import sysconfig; print(sysconfig.get_path('purelib'))")
DEST_SITE="${PKG_DIR}${SITE_PKG}"
mkdir -p "${DEST_SITE}"
pip install --target="${DEST_SITE}" vdf --no-deps 2>/dev/null || true

# Desktop integration
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/512x512/apps"
mkdir -p "${PKG_DIR}/usr/share/metainfo"
mkdir -p "${PKG_DIR}/usr/share/licenses/${PKG_NAME}"

cp easy_scsmodmanager/resources/${APP_ID}.desktop \
    "${PKG_DIR}/usr/share/applications/"
cp easy_scsmodmanager/resources/icon.svg \
    "${PKG_DIR}/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
cp easy_scsmodmanager/resources/icon.png \
    "${PKG_DIR}/usr/share/icons/hicolor/512x512/apps/${APP_ID}.png"
cp easy_scsmodmanager/resources/${APP_ID}.metainfo.xml \
    "${PKG_DIR}/usr/share/metainfo/"
cp LICENSE "${PKG_DIR}/usr/share/licenses/${PKG_NAME}/"

# DEBIAN control files
mkdir -p "${PKG_DIR}/DEBIAN"
cat > "${PKG_DIR}/DEBIAN/control" << EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: games
Priority: optional
Architecture: all
Maintainer: SwitchBros <switchbros@proton.me>
Homepage: https://github.com/Switch-Bros/easy-scsmodmanager
Description: Mod and profile manager for Euro Truck Simulator 2 and ATS
 Looks like the in-game mod manager but adds search, drag and drop activation,
 grouped load order with compatibility and conflict hints, map combo
 export/import, favourites, profile backup/restore and an ETS2/ATS switcher.
 Fully bilingual (English/German).
Depends: python3 (>= 3.13),
 python3-pyqt6,
 python3-pil,
 python3-pycryptodome,
 python3-httpx
EOF

cat > "${PKG_DIR}/DEBIAN/postinst" << 'EOF'
#!/bin/sh
set -e
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
EOF
chmod 755 "${PKG_DIR}/DEBIAN/postinst"

cat > "${PKG_DIR}/DEBIAN/postrm" << 'EOF'
#!/bin/sh
set -e
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
EOF
chmod 755 "${PKG_DIR}/DEBIAN/postrm"

dpkg-deb --build --root-owner-group "${PKG_DIR}"
mv "dist/deb-build/${PKG_NAME}_${VERSION}_all.deb" dist/

echo "Created: dist/${PKG_NAME}_${VERSION}_all.deb"
