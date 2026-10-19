{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.programs.claude-computer-use;
  home = config.home.homeDirectory;
  # Both apps rewrite these files themselves, so merge the one server entry in
  # place instead of owning the whole file.
  registerServer = pkgs.writers.writePython3 "register-computer-use-hyprland" { } ''
    import json
    import os
    import sys

    path, command = sys.argv[1], sys.argv[2]
    entry = {"type": "stdio", "command": command, "args": [], "env": {}}
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    servers = data.setdefault("mcpServers", {})
    if servers.get("computer-use-hyprland") != entry:
        servers["computer-use-hyprland"] = entry
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".hm-tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o777)
        os.replace(tmp, path)
  '';
in
{
  options.programs.claude-computer-use = {
    registerClaudeCode = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Register the server at user scope in ~/.claude.json for Claude Code.";
    };

    registerClaudeDesktop = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Register the server in Claude Desktop's claude_desktop_config.json.";
    };

    command = lib.mkOption {
      type = lib.types.str;
      default = "/run/current-system/sw/bin/claude-computer-use";
      description = ''
        Server executable. The default is the path the NixOS module installs,
        which stays stable across rebuilds.
      '';
    };
  };

  # Registered as "computer-use-hyprland": Claude Code reserves "computer-use".
  config.home.activation.registerClaudeComputerUse = lib.hm.dag.entryAfter [ "writeBoundary" ] (
    lib.optionalString cfg.registerClaudeCode ''
      run ${registerServer} ${home}/.claude.json ${lib.escapeShellArg cfg.command}
    ''
    + lib.optionalString cfg.registerClaudeDesktop ''
      run ${registerServer} ${config.xdg.configHome}/Claude/claude_desktop_config.json ${lib.escapeShellArg cfg.command}
    ''
  );
}
