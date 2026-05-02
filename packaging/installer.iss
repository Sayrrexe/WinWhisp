; Inno Setup script — WinWhisp installer.
; Build: iscc /DAppVersion=X.Y.Z packaging\installer.iss
; Перед сборкой: uv run pyinstaller --clean packaging\transcrb.spec (dist\winwhisp\).

#define AppName        "WinWhisp"
#ifndef AppVersion
  #define AppVersion   "0.1.4"
#endif
#define AppPublisher   "Sayrrexe"
#define AppExeName     "winwhisp.exe"
#define AppId          "{{8B6F4E2A-9B1D-4F3C-9E7B-3D2A1C4F5A60}"
#define AppRepoUrl     "https://github.com/Sayrrexe/WinWhisp"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppSupportURL={#AppRepoUrl}
AppUpdatesURL={#AppRepoUrl}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=WinWhisp-{#AppVersion}-setup
Compression=lzma2/ultra
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline dialog
WizardStyle=modern
SetupIconFile=..\resources\icon.ico
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Запускать {#AppName} при входе в Windows"; GroupDescription: "Автозапуск:"; Flags: unchecked

[Files]
Source: "..\dist\winwhisp\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\winwhisp\*"; DestDir: "{app}"; Excludes: "{#AppExeName}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить {#AppName}"; Flags: nowait postinstall skipifsilent
