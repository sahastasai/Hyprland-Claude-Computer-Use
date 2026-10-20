# Hyprland Claude Computer Use

Claude Desktop with computer use created by Opus 5.5, fully working on Hyprland.

Anthropic's Linux Claude Desktop beta ships without computer use, and Claude
Code's built-in `computer-use` server is macOS-only. This flake installs the
official Linux Claude Desktop and adds `computer-use-hyprland`, an MCP server
with the same tools as the built-in one, for both Claude Desktop and the
Claude Code CLI.

## Tools

Same names and parameters as Claude's built-in computer-use server:

`request_access`, `screenshot`, `zoom`, `left_click`, `double_click`,
`triple_click`, `right_click`, `middle_click`, `type`, `key`, `scroll`,
`left_click_drag`, `mouse_move`, `open_application`, `switch_display`,
`list_granted_applications`, `read_clipboard`, `write_clipboard`, `wait`,
`cursor_position`, `hold_key`, `left_mouse_down`, `left_mouse_up`,
`computer_batch`.

They behave like the built-in server:

- **Per-app approval.** `request_access` opens a desktop dialog listing each
  app. Clipboard access and Super-key shortcuts are separate checkboxes.
- **Full control.** Every app you approve can be clicked, typed into and
  driven with key combos, browsers and terminals included. Set
  `tiers = "strict"` for the macOS tiers instead: browsers `read` (visible
  only), terminals and IDEs `click` (left-click and scroll only).
- **Redaction.** Windows of apps you haven't approved are blacked out in
  screenshots, and input aimed at them is refused.
- **Guidance.** The server sends the built-in server's usage rules (tool
  choice, access flow, link safety, no money movement) as MCP instructions.

## Hyprland support

- **Workspaces.** Screenshots show the focused monitor's active workspace plus
  any open special workspace. Each screenshot lists approved apps on other
  workspaces, and `open_application` jumps to the app's workspace (or launches
  it).
- **Monitors.** `switch_display` takes a monitor name (`eDP-1`, `DP-2`, ...) or
  `auto`. Scaled and rotated monitors are mapped correctly.
- **Session discovery.** The server finds the live Hyprland instance and
  Wayland socket even when Claude Desktop starts with a stale environment.

| Job | Tool |
| --- | --- |
| Screenshots | `grim`, Pillow |
| Pointer position | `hyprctl dispatch movecursor` |
| Buttons, wheel, key combos | `ydotool` (uinput) |
| Text | `wtype` (full Unicode) |
| Windows and workspaces | `hyprctl` |
| Approval dialog | `zenity` |
| Clipboard | `wl-clipboard` |

## Install

```nix
{
  inputs.hyprland-claude.url = "github:sahastasai/Hyprland-Claude-Computer-Use";

  outputs = { nixpkgs, home-manager, hyprland-claude, ... }: {
    nixosConfigurations.my-host = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        hyprland-claude.nixosModules.default
        {
          nixpkgs.config.allowUnfree = true;   # Claude Desktop is unfree
          programs.hyprland.enable = true;
          programs.claude-computer-use = {
            enable = true;
            users = [ "alice" ];               # joins the ydotool group
          };
        }
        home-manager.nixosModules.home-manager
        {
          home-manager.users.alice.imports = [ hyprland-claude.homeManagerModules.default ];
        }
      ];
    };
  };
}
```

Then:

1. Run `sudo nixos-rebuild switch`.
2. Log out and back in so the `ydotool` group applies. Check with `id -nG`.
3. Run `claude mcp list` and confirm `computer-use-hyprland … ✔ Connected`.
   Claude Desktop picks the server up from `claude_desktop_config.json`.

### Options

NixOS (`programs.claude-computer-use`):

| Option | Default | Meaning |
| --- | --- | --- |
| `enable` | `false` | Install the server and enable `ydotoold`. |
| `users` | `[ ]` | Users added to the `ydotool` group. |
| `installClaudeDesktop` | `true` | Also install Claude Desktop (FHS build). |
| `tiers` | `"full"` | `"full"`: control every approved app. `"strict"`: macOS tiers. |
| `package` | built against `programs.hyprland.package` | Server package. |

Home Manager (`programs.claude-computer-use`):

| Option | Default | Meaning |
| --- | --- | --- |
| `registerClaudeCode` | `true` | Merge the server into `~/.claude.json`. |
| `registerClaudeDesktop` | `true` | Merge it into `~/.config/Claude/claude_desktop_config.json`. |
| `command` | `/run/current-system/sw/bin/claude-computer-use` | Server executable. |

Registration merges a single `mcpServers.computer-use-hyprland` entry and
leaves the rest of each file alone.

### Without the modules

```sh
nix run github:sahastasai/Hyprland-Claude-Computer-Use   # MCP server on stdio
claude mcp add -s user computer-use-hyprland -- "$(nix build --print-out-paths github:sahastasai/Hyprland-Claude-Computer-Use)/bin/claude-computer-use"
```

Input still needs a running `ydotoold` that your user can reach. Set
`CLAUDE_COMPUTER_USE_TIERS=strict` in the server's environment for the macOS
tiers.

## Notes

- The server is named `computer-use-hyprland` because Claude Code rejects
  user-configured servers named `computer-use` ("reserved MCP server name").
  Tools appear as `mcp__computer-use-hyprland__*`.
- Use `ctrl` shortcuts. Super-key combos control Hyprland itself and need
  `systemKeyCombos` approval.
- Claude Desktop itself is granted at `read` tier, so on-screen content can't
  drive the agent through its own window.

## Tested

Tested on Hyprland 0.55 with NixOS 26.05:

- the approval dialog, through a Claude Code `claude -p` session;
- `open_application` jumping across workspaces;
- Unicode typing;
- key combos, clicks, triple-click, drag-select and scroll direction;
- typing and key combos in a terminal at the default full tier;
- redaction, and the read-only Claude Desktop window.

Not yet tested: setups with more than one monitor, and use from inside Claude
Desktop itself.

## License

MIT. Claude Desktop is Anthropic's proprietary software, fetched from
Anthropic by the `claude-desktop-debian` flake; it is not part of this repo.
