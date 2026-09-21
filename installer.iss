; Inno Setup script for Jacon PPS Report.
;
; Builds a standard step-by-step Windows installer (Welcome -> install
; location -> shortcuts -> install -> finish) around the PyInstaller
; output in dist/, with a proper uninstaller registered in
; "Add or Remove Programs" (Inno Setup does this automatically via the
; AppId below, and needs no extra scripting).
;
; Build with build.spec FIRST (this only packages dist/, it doesn't run
; PyInstaller itself):
;   pyinstaller build.spec
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
;
; Output: installer_output\<name> Setup <version>.exe

#define MyAppName "Jacon PPS Report"
#define MyAppExeName "Jacon PPS Report.exe"
#define MyAppSourceDir "dist\Jacon PPS Report"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "Jacon Equipment"

[Setup]
; Fixed AppId — keep this the same across versions so an upgrade install
; replaces the previous one instead of installing side-by-side.
AppId={{81E5EDF6-AAF3-4B4A-A0F9-346A757E5219}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename={#MyAppName} Setup {#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Installing to Program Files and writing an HKLM uninstall entry both
; require admin rights; the optional Defender-exclusion task below does too.
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "defenderexclusion"; Description: "Add a Windows Defender exclusion for the install folder (recommended — avoids a slow antivirus scan the first time the app is launched)"; GroupDescription: "Startup performance:"

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Add-MpPreference -ExclusionPath '{app}'"""; StatusMsg: "Configuring Windows Defender exclusion…"; Tasks: defenderexclusion; Flags: runhidden
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Best-effort cleanup: remove the exclusion again if it was added at install
; time. Silently continues if it was never added or PowerShell fails.
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Remove-MpPreference -ExclusionPath '{app}' -ErrorAction SilentlyContinue"""; Flags: runhidden; RunOnceId: "RemoveDefenderExclusion"
