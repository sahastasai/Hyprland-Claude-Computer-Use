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

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ../pkgs/computer-use-hyprland {
        hyprland = config.programs.hyprland.package;
        inherit (cfg) tiers;
      };
      defaultText = lib.literalExpression "computer-use-hyprland built against programs.hyprland.package with cfg.tiers";
      description = "The computer-use-hyprland package.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [
      cfg.package
    ]
    ++ lib.optional cfg.installClaudeDesktop
      claude-desktop.packages.${pkgs.stdenv.hostPlatform.system}.default;

    # Pointer buttons, wheel and key combos go through a uinput virtual device
    # owned by ydotoold; group membership grants access to its socket.
    programs.ydotool.enable = true;
    users.users = lib.genAttrs cfg.users (_: {
      extraGroups = [ config.programs.ydotool.group ];
    });
  };
}
