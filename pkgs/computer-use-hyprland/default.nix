{
  lib,
  writeShellApplication,
  python3,
  grim,
  ydotool,
  wtype,
  wl-clipboard,
  zenity,
  libnotify,
  gtk3,
  hyprland,
}:

# Hyprland computer-use MCP server shared by Claude Code and Claude Desktop.
let
  python = python3.withPackages (ps: [ ps.pillow ]);
in
writeShellApplication {
  name = "claude-computer-use";
  runtimeInputs = [
    grim
    ydotool
    wtype
    wl-clipboard
    zenity
    libnotify
    gtk3
    hyprland
  ];
  text = ''
    export CLAUDE_CU_GTK_LAUNCH=${lib.getExe' gtk3 "gtk-launch"}
    exec ${lib.getExe python} -I ${./server.py} "$@"
  '';
}
