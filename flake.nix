{
  description = "Claude Desktop with computer use created by Opus 5.5, fully working on Hyprland";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

    # Anthropic's official Linux Claude Desktop .deb, repackaged for Nix.
    claude-desktop = {
      url = "github:aaddrick/claude-desktop-debian";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{
      self,
      nixpkgs,
      ...
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems =
        f:
        nixpkgs.lib.genAttrs systems (
          system:
          f (
            import nixpkgs {
              inherit system;
              config.allowUnfree = true;
            }
          )
        );
    in
    {
      packages = forAllSystems (pkgs: rec {
        computer-use-hyprland = pkgs.callPackage ./pkgs/computer-use-hyprland { };
        claude-desktop = inputs.claude-desktop.packages.${pkgs.stdenv.hostPlatform.system}.default;
        default = computer-use-hyprland;
      });

      nixosModules.default = import ./modules/nixos.nix { inherit (inputs) claude-desktop; };
      homeManagerModules.default = ./modules/home-manager.nix;

      checks = forAllSystems (pkgs: {
        computer-use-hyprland = self.packages.${pkgs.stdenv.hostPlatform.system}.computer-use-hyprland;
        nixos-module =
          (nixpkgs.lib.nixosSystem {
            inherit (pkgs.stdenv.hostPlatform) system;
            modules = [
              self.nixosModules.default
              {
                programs.hyprland.enable = true;
                programs.claude-computer-use = {
                  enable = true;
                  users = [ "alice" ];
                };
                users.users.alice.isNormalUser = true;
                nixpkgs.config.allowUnfree = true;
                boot.loader.grub.enable = false;
                fileSystems."/" = {
                  device = "none";
                  fsType = "tmpfs";
                };
                system.stateVersion = "26.05";
              }
            ];
          }).config.system.build.toplevel;
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt);
    };
}
