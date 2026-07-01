; gitmove Windows installer (Inno Setup 6+)
; Build: scripts/build_installer.ps1  or  python scripts/build_installer.py

#ifndef MyAppVersion
  #define MyAppVersion "0.5.1"
#endif

#define MyAppName "gitmove"
#define MyAppPublisher "gitmove"
#define MyAppURL "https://github.com/MyLoveou/gitmove"
#define MyAppExeCLI "gitmove.exe"
#define MyAppExeGUI "gitmove-gui.exe"

[Setup]
AppId={{8F4E2A91-3C7D-4B2E-9F1A-6D5E8C0B4A72}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\artifacts
OutputBaseFilename=gitmove-{#MyAppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeGUI}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon} (gitmove GUI)"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addpath"; Description: "将 gitmove 安装目录加入系统 PATH（推荐，便于在任意终端使用 gitmove 命令）"; GroupDescription: "附加选项:"; Flags: checkedonce

[Files]
Source: "..\..\dist\{#MyAppExeCLI}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\dist\{#MyAppExeGUI}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\gitmove GUI"; Filename: "{app}\{#MyAppExeGUI}"
Name: "{group}\gitmove 命令行"; Filename: "{cmd}"; Parameters: "/K ""{app}\{#MyAppExeCLI}"" --help"
Name: "{autodesktop}\gitmove GUI"; Filename: "{app}\{#MyAppExeGUI}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeGUI}"; Description: "启动 gitmove GUI"; Flags: nowait postinstall skipifsilent

[Code]
procedure EnvAddPath(InstallPath: string);
var
  Paths: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path', Paths)
  then
    Paths := '';
  if Pos(';' + UpperCase(InstallPath) + ';', ';' + UpperCase(Paths) + ';') = 0 then
  begin
    if Paths <> '' then
      Paths := Paths + ';';
    Paths := Paths + InstallPath;
    RegWriteStringValue(HKEY_LOCAL_MACHINE,
      'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'Path', Paths);
  end;
end;

procedure EnvRemovePath(InstallPath: string);
var
  Paths, P: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path', Paths)
  then
    exit;
  P := ';' + Paths + ';';
  StringChangeEx(P, ';' + InstallPath + ';', ';', True);
  if Length(P) > 0 then
    Delete(P, 1, 1);
  if (Length(P) > 0) and (P[Length(P)] = ';') then
    Delete(P, Length(P), 1);
  RegWriteStringValue(HKEY_LOCAL_MACHINE,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path', P);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if IsTaskSelected('addpath') then
      EnvAddPath(ExpandConstant('{app}'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    EnvRemovePath(ExpandConstant('{app}'));
end;
