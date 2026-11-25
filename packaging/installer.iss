; Inno Setup script -> "AI Animator Setup.exe"
; Build: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
#define AppName "AI Animator"
#define AppVersion "0.2.0"
#define AppExe "AI Animator.exe"

[Setup]
AppId={{8C1F3A52-6B7E-4D2A-9E55-3F1D2C7A9B10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
SetupIconFile=..\ai_animator\resources\icon.ico
OutputDir=..\dist
OutputBaseFilename=AI Animator Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; per-user install by default, no admin needed; user can choose all-users
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\AI Animator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; User projects (Documents\AI Animator Projects), settings (%APPDATA%\AI Animator) and the
; API key (Credential Manager) are intentionally NOT removed on uninstall.
