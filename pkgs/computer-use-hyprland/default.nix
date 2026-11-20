{
  lib,
  symlinkJoin,
  writeShellApplication,
  python3,
  grim,
  ydotool,
  wtype,
  wlrctl,
  wl-clipboard,
  zenity,
  libnotify,
  gtk3,
  hyprland,
  # "full": every approved app is controllable; "strict": macOS-style tiers.
  tiers ? "full",
  # Grant every app without the approval dialog (Claude Desktop stays read-only).
  # Off by default; CLAUDE_CU_AUTO_GRANT=1 in the server's environment also turns it on.
  autoGrant ? false,
  # Auto-grant only these apps (others still get the dialog); empty = all.
  autoGrantAllow ? [ ],
  # Never grant these apps in auto-grant mode.
  autoGrantDeny ? [ ],
}:

# Hyprland computer-use MCP server shared by Claude Code and Claude Desktop,
# plus `claude-cu` (revoke / restore / status / log).
let
  python = python3.withPackages (ps: [ ps.pillow ]);
  exportList =
    name: list:
    lib.optionalString (list != [ ]) ''
      export ${name}="''${${name}:-${lib.concatStringsSep "," list}}"
    '';

  server = writeShellApplication {
    name = "claude-computer-use";
    runtimeInputs = [
      grim
      ydotool
      wtype
      wlrctl
      wl-clipboard
      zenity
      libnotify
      gtk3
      hyprland
    ];
    text = ''
      export CLAUDE_COMPUTER_USE_TIERS=${tiers}
      export CLAUDE_CU_GTK_LAUNCH=${lib.getExe' gtk3 "gtk-launch"}
    ''
    + lib.optionalString autoGrant ''
      export CLAUDE_CU_AUTO_GRANT="''${CLAUDE_CU_AUTO_GRANT:-1}"
    ''
    + exportList "CLAUDE_CU_ALLOW" autoGrantAllow
    + exportList "CLAUDE_CU_DENY" autoGrantDeny
    + ''
      exec ${lib.getExe python} -I ${./server.py} "$@"
    '';
  };

  cli = writeShellApplication {
    name = "claude-cu";
    text = ''
      exec ${lib.getExe python} -I ${./server.py} cli "$@"
    '';
  };
in
symlinkJoin {
  name = "computer-use-hyprland";
  paths = [
    server
    cli
  ];
  passthru = { inherit python; };
  meta.mainProgram = "claude-computer-use";
}
