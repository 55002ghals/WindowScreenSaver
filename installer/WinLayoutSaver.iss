; Inno Setup script — wraps PyInstaller dist into WinLayoutSaverSetup.exe
; Compile:  ISCC.exe installer\WinLayoutSaver.iss
; Output:   installer\Output\WinLayoutSaverSetup.exe

#define MyAppName        "WinLayoutSaver"
#define MyAppExeName     "WinLayoutSaver.exe"
#define MyAppPublisher   "WinLayoutSaver"
#define MyAppURL         "https://github.com/"
; AppVersion is overridden from build.bat with /DMyAppVersion=...
#ifndef MyAppVersion
  #define MyAppVersion   "1.0.0"
#endif

[Setup]
AppId={{D7E5F7B8-9A4C-4F3E-8B5A-3C2F1D8E7A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Per-user install — no admin elevation required.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=WinLayoutSaverSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Uninstaller appears in Apps & Features.
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean";  MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Pull the entire PyInstaller onedir output.
Source: "..\dist\WinLayoutSaver\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Best-effort: remove any scheduled rollback task on uninstall (ignore failure).
Filename: "schtasks.exe"; Parameters: "/Delete /TN WinLayoutSaver_Rollback /F"; Flags: runhidden; RunOnceId: "DelTask"
