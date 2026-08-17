# ❓ Frequently Asked Questions

---

## General

### Is this affiliated with SCS Software or Steam?

No. Easy SCSModManager is an independent tool. It only edits your own
`profile.sii` and reads your own installed mods.

### Which games are supported?

Euro Truck Simulator 2 and American Truck Simulator. Switch between them from the
**Game** menu.

### Does it work with Workshop mods?

Yes - it reads both your local `mod/` folder and the Steam Workshop content for
the game.

## Activation and order

### Why did my activated mod not jump to the top?

By design. Activating a mod drops it into the bottom of its own load-order
group, so it never renders under another group's header. Top of the list is
highest priority.

### A mod has an orange border - what does that mean?

It sits in the wrong load-order group. Right-click it and pick **Move to** ->
its group, or **Automatic (own category)**. Dragging it into the right section
does the same.

## Conflicts

### What do the ⚠ and ⊘ glyphs mean?

A conflict means two active mods change the same `def/` file; the higher one
wins. **⚠ (yellow)** = the mod loses some of its files to mods above it.
**⊘ (red)** = it loses all of them and effectively does nothing where it sits.
**= (grey)** = it touches files that many mods change at once, which is usually
intended and never counted as a conflict. No glyph = it wins everything. Hover
for the file list and the winners.

### Is a conflict an error?

No, it is a hint. For maps an overlap is often intentional and the load order
resolves it.

### The tooltip says "... and 82 more files". How do I see them all?

Right-click the mod and choose **Show all conflicts...**. The dialog lists every
overwritten file without a cap and can switch to all flagged mods at once. Use
**Copy all** or **Save to file...** if you want to share the list.

## Deleting

### Where do deleted mods go?

To your system trash, so you can restore them. Local mods only - Workshop mods
are managed by Steam (unsubscribe in the Workshop to remove them).

## Saving

### Why must the game be closed when I save?

The game rewrites `profile.sii` when it exits, which would overwrite your saved
order. Close the game first.

## Troubleshooting

### My game / Workshop mods are not detected.

Open **File -> Settings** and set the path overrides for the documents and
Workshop folders. On Windows the app reads the registry to find Steam and the
Documents folder; if you moved them, a manual override fixes it. **Tools -> Open
Log Folder** shows a log that names what was and was not found.
