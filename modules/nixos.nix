{ claude-desktop }:

{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.programs.claude-computer-use;
in
{
  options.programs.claude-computer-use = {
    enable = lib.mkEnableOption "the Hyprland computer-use MCP server for Claude";

    users = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "alice" ];
      description = ''
        Users allowed to inject input. They join the ydotool group, which owns
        the ydotoold socket; log out and back in after the first switch.
      '';
    };

    installClaudeDesktop = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Also install Anthropic's official Linux Claude Desktop (FHS build).";
    };

    tiers = lib.mkOption {
      type = lib.types.enum [
        "full"
        "strict"
      ];
      default = "full";
      description = ''
        "full" lets Claude click and type in every app you approve, browsers and
        terminals included; Claude Desktop's own window stays read-only.
        "strict" uses the macOS tiers: browsers read-only, terminals and IDEs
        click-only.
      '';
    };

    autoGrant = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Skip the approval dialog: request_access and every action succeed for
        every app (Claude Desktop's own window stays read-only). Meant for a
        machine dedicated to an agent. Every call is written to
        ~/.local/state/claude-computer-use/audit.jsonl, and `claude-cu revoke`
        disables all actions until `claude-cu restore`.
      '';
    };

    autoGrantAllow = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [
        "firefox"
        "kitty"
      ];
      description = "With autoGrant, auto-grant only these apps (names, desktop ids or window classes); others still get the dialog. Empty means all.";
    };

    autoGrantDeny = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "org.keepassxc.KeePassXC" ];
      description = "With autoGrant, never grant these apps.";
    };

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ../pkgs/computer-use-hyprland {
        hyprland = config.programs.hyprland.package;
        inherit (cfg)
          tiers
          autoGrant
          autoGrantAllow
          autoGrantDeny
          ;
      };
      defaultText = lib.literalExpression "computer-use-hyprland built against programs.hyprland.package with cfg.tiers and cfg.autoGrant*";
      description = "The computer-use-hyprland package.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      cfg.package
    ]
    ++
      lib.optional cfg.installClaudeDesktop
        claude-desktop.packages.${pkgs.stdenv.hostPlatform.system}.default;

    # Pointer buttons, wheel and key combos go through a uinput virtual device
    # owned by ydotoold; group membership grants access to its socket.
    programs.ydotool.enable = true;
    users.users = lib.genAttrs cfg.users (_: {
      extraGroups = [ config.programs.ydotool.group ];
    });
  };
}
