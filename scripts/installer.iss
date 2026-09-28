;;; فریلنس‌یار آرنا — اسکریپت نصب‌کننده‌ی ویندوز (Inno Setup 6)
#define MyAppName "فریلنس‌یار آرنا"
#define MyAppPublisher "Arena"
#define MyAppVersion "1.0.0"
#define MyAppExeName "frilanser-gui.exe"

[Setup]
AppId={{7F2B4E1A-9C3D-4A5E-8B6F-1D2C3E4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/saeidkazemi1989-bot/frilanser
DefaultDirName={autopf}\Frilanser
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=Frilanser-Setup
ArchitecturesInstallIn64BitMode=x64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "ایجاد میان‌بر روی دسکتاپ"; GroupDescription: "میان‌برها:"; Flags: unchecked

[Files]
Source: "dist\frilanser-gui.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\frilanser.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "data\raw\*"; DestDir: "{app}\data\raw"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\خط فرمان فریلنس‌یار"; Filename: "{cmd}"; Parameters: "/k cd /d ""{app}"" & frilanser.exe --help"
Name: "{group}\راهنما"; Filename: "{app}\README.md"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "اجرای برنامه پس از نصب"; Flags: postinstall nowait skipifsilent
