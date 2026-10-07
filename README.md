# Notes for Krita
A Krita plugin that implements a dockable panel (docker) featuring a list of persistent notes or tasks per document, with support for colors, completion status, and drag-and-drop reordering.

- This plugin was created based on Grum999's Buli Notes, but reimplemented in my own way.
https://github.com/Grum999/BuliNotes 

## Characteristics

- Document-specific persistent notes: Each .kra file stores its own notes within the document itself using annotations, so they travel with the file.

- Custom colors: 8 color options (None, Red, Orange, Yellow, Green, Blue, Purple, Gray) with automatic text contrast (white or black, depending on brightness).

- Each note has a checkbox that applies a strikethrough and dims the text.
  
- Drag notes within the list or use the ↑ / ↓ buttons.

- Inline editing: Double-click a note to edit it directly.

- Collapsible panel: The ▼ / ▶ button minimizes the docker to save screen space.

- Safe saving when switching documents: If there are pending changes and you switch canvases, the data is saved before the new document's notes are loaded.

IMPORTANT! 👋
Notes are saved within the .kra file as an annotation. This means that:

You must save the document for the notes to be preserved on disk.

If you close Krita without saving the .kra file, the notes will be lost.

# Plugin activation
It is activated in the Krita settings.
<img width="1005" height="700" alt="image" src="https://github.com/user-attachments/assets/d37feee7-2282-46fa-b3d0-d2aa1e38541a" />


## how to use the tool
The plugin appears as a dockable panel on the right side of Krita.
- New task/note: type the text in the top field and click Add (or press Enter).

- Note color: select a color from the dropdown menu before adding, or select an existing note and change its color to apply the new one.

- Mark as done: click the note's checkbox. The text will be crossed out and dimmed.
  
- Edit a note: double-click the text.

- Reorder: drag the note or use the ↑ / ↓ buttons.

- Delete: select a note and click Delete, or use Clear to remove all notes (requires confirmation).

- Minimize: click the ▼ button in the header to collapse the panel.

<img width="271" height="249" alt="image" src="https://github.com/user-attachments/assets/43a28f32-74bc-4307-963c-19d45b23ac7d" />
<img width="50" height="53" alt="image" src="https://github.com/user-attachments/assets/d474c527-0001-458e-9c7e-96c16f9496ab" />
<img width="272" height="237" alt="image" src="https://github.com/user-attachments/assets/fb52ebb1-de16-41b7-9c6c-861e9ab06135" />


https://github.com/user-attachments/assets/da401c64-2ef0-440b-8874-b6eba27f9072


## Installation

The current version of the plugin is built for Krita 5.3.4.1
You can download the latest version of the plugin from the releases page.

## Plugin installation
Since version 2.0, the plugin can be installed as a Python extension. In Krita, go to Tools › Scripts › Import Python Plugin from File... and select the .zip file you downloaded.

<img width="898" height="387" alt="image" src="https://github.com/user-attachments/assets/ed18afe3-3508-47ad-a121-904aefe65164" />

## Authors

- [@Orquoest](https://github.com/Orquoest)
- [@Orquoest](https://github.com/Orquoest1233)
