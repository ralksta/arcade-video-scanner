#!/bin/bash
# ──────────────────────────────────────────────────────────────────
# Installs the "Optimize Video (HEVC)" Quick Action for Finder
# Run once: ./install-finder-action.sh
#
# The encoder lives in the separate videocrunch repo since the split; this
# installer bakes the resolved path to its videocrunch.py (formerly
# scripts/video_optimizer.py) into the workflow.
#
# Uninstall: rm -rf "$HOME/Library/Services/Optimize Video (HEVC).workflow"
# ──────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WORKFLOW_NAME="Optimize Video (HEVC)"
WORKFLOW_DIR="$HOME/Library/Services/${WORKFLOW_NAME}.workflow"

# ── Resolve the videocrunch checkout ──────────────────────────────
# Same resolution the server uses (arcade_scanner/config.py optimizer_path)
# and the same as scan-folder-from-finder.sh:
# ARCADE_OPTIMIZER_PATH (legacy) > VIDEOCRUNCH_PATH > sibling checkout.
if [ -n "${ARCADE_OPTIMIZER_PATH:-}" ]; then
    OPTIMIZER="$ARCADE_OPTIMIZER_PATH"
elif [ -n "${VIDEOCRUNCH_PATH:-}" ]; then
    OPTIMIZER="$VIDEOCRUNCH_PATH"
else
    OPTIMIZER="$(dirname "$PROJECT_DIR")/videocrunch/videocrunch.py"
fi
VC_DIR="$(dirname "$OPTIMIZER")"

if [ ! -f "$OPTIMIZER" ]; then
    echo "❌ videocrunch not found at $OPTIMIZER"
    echo "   Clone it as a sibling checkout (../videocrunch) or set VIDEOCRUNCH_PATH."
    exit 1
fi

# Prefer videocrunch's own virtualenv; fall back to whatever python3 is on PATH.
PYTHON="$VC_DIR/.venv/bin/python3"
if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi

# Remove existing workflow if present
if [ -d "$WORKFLOW_DIR" ]; then
    echo "♻️  Replacing existing workflow..."
    rm -rf "$WORKFLOW_DIR"
fi

# Create workflow bundle structure
mkdir -p "$WORKFLOW_DIR/Contents"

# 1. Info.plist — marks this as an Automator workflow
cat > "$WORKFLOW_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>NSServices</key>
    <array>
        <dict>
            <key>NSMenuItem</key>
            <dict>
                <key>default</key>
                <string>Optimize Video (HEVC)</string>
            </dict>
            <key>NSMessage</key>
            <string>runWorkflowAsService</string>
            <key>NSSendFileTypes</key>
            <array>
                <string>public.movie</string>
                <string>public.mpeg-4</string>
                <string>com.apple.quicktime-movie</string>
                <string>public.avi</string>
                <string>org.matroska.mkv</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
PLIST

# 2. document.wflow — the actual workflow definition
cat > "$WORKFLOW_DIR/Contents/document.wflow" << WFLOW
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>AMApplicationBuild</key>
	<string>523</string>
	<key>AMApplicationVersion</key>
	<string>2.10</string>
	<key>AMDocumentVersion</key>
	<string>2</string>
	<key>actions</key>
	<array>
		<dict>
			<key>action</key>
			<dict>
				<key>AMAccepts</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Optional</key>
					<false/>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.path</string>
					</array>
				</dict>
				<key>AMActionVersion</key>
				<string>1.0.2</string>
				<key>AMApplication</key>
				<array>
					<string>Automator</string>
				</array>
				<key>AMBundleIdentifier</key>
				<string>com.apple.RunShellScript</string>
				<key>AMCategory</key>
				<array>
					<string>AMCategoryUtilities</string>
				</array>
				<key>AMIconName</key>
				<string>TerminalIcon</string>
				<key>AMKeywords</key>
				<array>
					<string>Shell</string>
					<string>Script</string>
					<string>Command</string>
					<string>Run</string>
					<string>Unix</string>
				</array>
				<key>AMName</key>
				<string>Run Shell Script</string>
				<key>AMProvides</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.string</string>
					</array>
				</dict>
				<key>ActionBundlePath</key>
				<string>/System/Library/Automator/Run Shell Script.action</string>
				<key>ActionName</key>
				<string>Run Shell Script</string>
				<key>ActionParameters</key>
				<dict>
					<key>COMMAND_STRING</key>
					<string>OPTIMIZER="$OPTIMIZER"
PYTHON="$PYTHON"

# Build quoted file list
FILES=""
for f in "\$@"; do
    FILES="\$FILES '\$f'"
done

osascript -e "
tell application \"Terminal\"
    activate
    do script \"'\$PYTHON' '\$OPTIMIZER' \$FILES; echo ''; echo 'Done. Press any key to close...'; read -n1\"
end tell
"</string>
					<key>CheckedForUserDefaultShell</key>
					<true/>
					<key>inputMethod</key>
					<integer>1</integer>
					<key>shell</key>
					<string>/bin/bash</string>
					<key>source</key>
					<string></string>
				</dict>
				<key>BundleIdentifier</key>
				<string>com.apple.RunShellScript</string>
				<key>CFBundleVersion</key>
				<string>1.0.2</string>
				<key>CanShowSelectedItemsWhenRun</key>
				<false/>
				<key>CanShowWhenRun</key>
				<true/>
				<key>Category</key>
				<array>
					<string>AMCategoryUtilities</string>
				</array>
				<key>Class Name</key>
				<string>RunShellScriptAction</string>
				<key>InputUUID</key>
				<string>A1B2C3D4-E5F6-7890-ABCD-EF1234567890</string>
				<key>Keywords</key>
				<array>
					<string>Shell</string>
					<string>Script</string>
					<string>Command</string>
					<string>Run</string>
					<string>Unix</string>
				</array>
				<key>Name</key>
				<string>Run Shell Script</string>
				<key>OutputUUID</key>
				<string>B2C3D4E5-F6A7-8901-BCDE-F12345678901</string>
			</dict>
			<key>isViewVisible</key>
			<integer>1</integer>
		</dict>
	</array>
	<key>connectors</key>
	<dict/>
	<key>workflowMetaData</key>
	<dict>
		<key>applicationBundleIDsByPath</key>
		<dict/>
		<key>applicationPaths</key>
		<array/>
		<key>inputTypeIdentifier</key>
		<string>com.apple.Automator.fileSystemObject</string>
		<key>outputTypeIdentifier</key>
		<string>com.apple.Automator.nothing</string>
		<key>presentationMode</key>
		<integer>15</integer>
		<key>processesInput</key>
		<integer>0</integer>
		<key>serviceInputTypeIdentifier</key>
		<string>com.apple.Automator.fileSystemObject</string>
		<key>serviceOutputTypeIdentifier</key>
		<string>com.apple.Automator.nothing</string>
		<key>workflowTypeIdentifier</key>
		<string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
WFLOW

echo ""
echo "✅ Quick Action installed: '$WORKFLOW_NAME'"
echo "📂 Location: $WORKFLOW_DIR"
echo ""
echo "Right-click any video in Finder → Quick Actions → $WORKFLOW_NAME"
echo "Engine: $OPTIMIZER"
echo "Python: $PYTHON"
echo ""
echo "Uninstall: rm -rf \"$WORKFLOW_DIR\""
echo ""
