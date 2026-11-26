# Screenshot checklist

What to capture, and the rules each capture has to satisfy.

## What the documented rules are

The only published screenshot specification is for **MCP App connector carousels**, on https://claude.com/docs/connectors/building/submission (retrieved 2026-11-25). Verbatim:

> "* **Format**: PNG
> * **Width**: at least 1000px
> * **Count**: 3–5 images
> * **Crop**: to the app response only, without the prompt in the image
> * **Aspect ratio**: any
> * **Paired prompts**: provide the prompt text separately for each screenshot
> * **Mobile**: no separate mobile assets are required, and one batch covers all surfaces
> * **Video or GIF**: not accepted"

`TODO(verify)`: no plugin submission page documents screenshot requirements for a **plugin bundle**. The rules above are the closest published specification, so they are the safe target. Whether a plugin bundle listing shows screenshots at all is not documented.

## The captures

Three captures, matching the three example prompts in [example-prompts.md](example-prompts.md).

### 1. The installed plugin

| Property | Value |
|---|---|
| What | Claude Code's `/plugin` panel showing the plugin, its MCP server and its 10 skills |
| Format | PNG |
| Width | At least 1000 px |
| Crop | The plugin panel. Not the terminal, not the user's desktop |
| Notes | The skill list must be readable at listing size, so capture at a resolution where the 10 skill names are legible |

### 2. A read-only result

| Property | Value |
|---|---|
| What | The result of the "clients with no internet access" prompt |
| Format | PNG |
| Width | At least 1000 px |
| Crop | The response only, without the prompt text in the image |
| Paired prompt | "Which clients on this site are connected but have no internet access right now? Show me the client, the AP it is on, and how long it has been failing." |
| Notes | Use a test controller with sample data. The capture must not contain a real site's client names, MAC addresses or topology |

### 3. The confirmation gate

| Property | Value |
|---|---|
| What | The agent proposing the guest WiFi VLAN change and asking for confirmation, with nothing written yet |
| Format | PNG |
| Width | At least 1000 px |
| Crop | The response only, without the prompt text in the image |
| Paired prompt | "The guest WiFi SSID needs a new VLAN. Show me the current guest network and SSID, then propose the change and wait for my confirmation before applying it. Do not change anything yet." |
| Notes | This is the capture that shows the safety model. It must show the agent waiting, not a completed change |

## Rules to follow

- **PNG.** Not JPEG, not WebP, not a video, not a GIF.
- **At least 1000 px wide.** Capture at a higher resolution and do not downscale below 1000 px.
- **3 to 5 images.** Three is enough. If you add a fourth, it must follow the same rules.
- **Crop to the response.** The prompt text must not be in the image; supply it separately.
- **No video and no GIF.**
- **One batch for all surfaces.** No separate mobile assets are needed.

## Privacy

- Use a test controller with sample data.
- Remove real client names, hostnames, MAC addresses, site names and IP ranges from every capture.
- Do not capture the terminal environment, a shell prompt that shows a path with a username, or a browser bar showing a private URL.
- Do not capture a screen that shows an API key. The plugin never displays one, but a terminal showing an `export` would.

## Icon

Separate from the screenshots, the plugin needs an icon.

| Property | Value |
|---|---|
| File | `.claude-plugin/icon.png` |
| Format | PNG. SVG and WebP are not accepted |
| Size | 1024 x 1024 px, square |
| Weight | 0.80 MB |
| Rule | Between 512 and 2048 px on each side, under 2 MB |

The icon is the repository's own logo, centred on a square canvas. `TODO(verify)`: the directory's published pages document no icon dimensions; the range above is what `claude plugin validate` reports it wants.

## Checklist

- [ ] Icon is a square PNG, 512-2048 px per side, under 2 MB
- [ ] 3 screenshots, PNG, each at least 1000 px wide
- [ ] Each screenshot cropped to the response, without the prompt in the image
- [ ] The three paired prompts written down separately
- [ ] No video, no GIF
- [ ] No real client, site or credential data in any capture
- [ ] The confirmation-gate capture shows the agent waiting, not a completed write
