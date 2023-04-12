# SteamVR OSC Integration

**This project is provided *as-is* without any accompanying avatar setup or menu icons. If you're looking for an easy way to set this up (including a video tutorial), you can purchase the Support Package on booth here: TBA**

A small utility to control a few SteamVR functions via OSC in order to expose them to VRChat.
It is essentially a bridge between OSC and the SteamVR debug commands (_SteamVR > Developer > Debug Commands_).

The actual command is triggered by sending an OSC packet with a single boolean parameter set to `true` to an address specified in a config file.
This makes it easily usable with VRChat Action Menu buttons or Contact Receivers.

## Installation

Simply go to the [Releases](https://github.com/jangxx/steamvr-osc-control/releases) and download the latest version as a zip file.
Extract this file to a directory of your liking and you are done.
Afterwards run steamvr_osc_control.exe in the unpacked directory.

### Updating

To update the program, simply delete all files from the previous installation and copy the files from the new version into the same folder.
The settings are kept in a different place, so it's always safe to completely delete the whole installation directory.
If you have enabled the SteamVR integration, the main executable should stay in the same place however.

## Tray Menu

Right clicking on the tray icon opens the following menu:

![Tray menu screenshot](/assets/gh_tray_menu.png)

- `Register with SteamVR` and `Unregister from SteamVR`: This option will load the application manifest into SteamVR (or remove it respectively), essentially making it aware of the location of the executable. This makes it show up in the list of possible Startup Overlay Apps and allows you to launch and close the app together with SteamVR.
- `Open config directory`: Does exactly what it says; it opens a Windows Explorer windows at the location of the config file.
- `Reload config`: Reloads the config and restarts the OSC server to bind to the address and port specified in the file.
- `Load config mapping from file`: Opens a file selection dialog, which allows you to pick a command mapping file to incorporate into the config file. See below for the format of this file.
- `Exit`: I don't think I need to explain this one.

## Config file

The config file is located in _%LocalAppData%\jangxx\SteamVR OSC Control_ and very simple:

```js
{
    "osc": {
        "listen_address": "127.0.0.1", // address the OSC server listens on
        "listen_port": 9001 // port the OSC server listens on
    },
    "command_mapping": {
        "/avatar/parameters/ParameterName": "<some command>", // mapping between the parameters and the debug commands
    }
}
```

Changes to the config file are not automatically applied, but the tray icon menu contains a button _Reload config_ to apply it without restarting.

To find the valid command names, open the SteamVR Debug command window, which you can find as follows:

![SteamVR Debug Commands](/assets/gh_steamvr_debug.png)

## Command mapping file

In order to simplify sharing and installing command mappings, the app has support for loading these mapping from external files.
The resulting mapping is then merged into the existing one from the config, overwriting existing commands if there is a conflict.

The format is a simple INI-like file, where the mapping is provided as keys and values, with the keys representing VRChat parameter names and the values being the respective debug commands, all within the `[mapping]` section.

An example config file could look like this:

```ini
[mapping]
ScreenshotButton = screenshot_request
DashboardButton = system_dashboard_toggle
```

which would then get turned into the following config:

```js
{
	"/avatar/parameters/ScreenshotButton": "screenshot_request",
	"/avatar/parameters/DashboardButton": "system_dashboard_toggle",
}
```