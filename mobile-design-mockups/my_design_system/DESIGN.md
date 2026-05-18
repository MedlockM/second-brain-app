# Amber Clarity Design System

### 1. Overview & Creative North Star
**Creative North Star: "The Illuminated Archive"**

Amber Clarity is a design system built for deep focus and long-form consumption. It rejects the frantic energy of modern social interfaces in favor of a "warm editorial" aesthetic. The system is defined by its use of high-contrast typography, generous whitespace (Spacing 3), and a signature amber accent that provides a sense of intellectual warmth. 

The layout breaks the rigid "template" look by using intentional typographic scale shifts and "floating" interactive zones that sit above the content, creating a layered, curated reading experience rather than a static webpage.

### 2. Colors
The palette is rooted in a warm-neutral base (`#fcf9f6`) to reduce eye strain, punctuated by a vibrant "Amber" primary color (`#ffcb05`).

- **Primary & Secondary:** The Amber primary is used sparingly for high-value interactions (CTAs, active states) and meaningful accents. The secondary tones are olive-greys that ground the interface.
- **The "No-Line" Rule:** Visual sectioning is achieved through color blocks and tonal shifts. Avoid 1px solid borders for broad layout divisions. For example, the segment control uses a subtle `surface_container` background against the main `surface` rather than a stroke.
- **Surface Hierarchy & Nesting:**
    - `Surface`: The canvas for long-form reading.
    - `Surface Container Low`: Background for secondary controls.
    - `Surface Container High`: Used for elevated elements like tags and metadata chips.
- **Signature Textures:** Use a 5% opacity tint of the Primary color (Amber) for callouts and blockquotes to create a "highlighted" tactile feel.

### 3. Typography
The system utilizes a refined scale that balances authority with legibility.

- **Scale Ground Truth:**
    - **Display/H1:** 32px (Bold, Tracking Tight) - Reserved for major entry points.
    - **Headline/H3:** 20px (1.25rem) - For section headers.
    - **Body:** 16px (1rem) - The standard for all long-form text, using a 1.6 line height for optimal readability.
    - **Small Labels/Metadata:** 13px - 14px - For tags and timestamp information.
- **Hierarchy:** Plus Jakarta Sans provides a clean, modern headline presence, while Inter handles the body text to ensure maximum clarity across all device resolutions.

### 4. Elevation & Depth
Elevation in Amber Clarity is soft and atmospheric, prioritizing layering over hard shadows.

- **The Layering Principle:** Use the `surface-container` tiers to stack information. For example, a tag sits on a `surface` background using a `surface_container_high` fill.
- **Ambient Shadows:** The system uses a specific `soft` shadow: `0 8px 24px rgba(43, 45, 66, 0.04)`. This shadow is nearly imperceptible but provides just enough lift to separate interactive layers from content.
- **Glassmorphism:** The Top Bar uses a `backdrop-blur-md` with 90% opacity (`#fcf9f6/90`) to maintain context of the content while scrolling.

### 5. Components
- **Segmented Control:** A pill-shaped container with a high-contrast active state. The active button uses the Primary Amber with Dark Text (`on-primary-container`) to stand out against the muted background.
- **Callout Aside:** A vertical 4px bar using the Primary color, paired with a 5% primary background. This creates an editorial "pull quote" effect.
- **Metadata Chips:** Pill-shaped (`rounded-full`) with a `surface` fill and a very subtle `outline-variant` (5% black) to give them a physical "sticker" feel.
- **Checklist Items:** Use the Primary color for icons (`check_circle`) to guide the eye through list-based data.

### 6. Do's and Don'ts
- **Do:** Use tight tracking on large display text (32px+) to give it a modern editorial punch.
- **Do:** Ensure a 1.6x line height on all body text to prevent "text crowding."
- **Don't:** Use pure black for text; use the `text-main` (`#2b2d42`) to maintain a soft, ink-on-paper feel.
- **Don't:** Over-apply shadows. Only the top bar and primary interactive containers should utilize the `soft` shadow.
- **Do:** Use the Primary Amber for selection states (`selection:bg-primary/30`) to create a cohesive brand experience during user interaction.