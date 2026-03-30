# Example Slide Templates

This directory contains example HTML slide templates demonstrating various layout patterns for Apple-inspired minimalist presentations. These templates showcase how to use the CSS variables and classes from the provided stylesheets.

## Available Templates

1. **hero-title.html** - Opening/title slide with centered text
2. **content-bullets.html** - Standard content slide with bullet points
3. **stat-focus.html** - Large number/statistic with context
4. **split-content.html** - Two-column layout with text and visual
5. **full-image.html** - Full-bleed image with overlay text
6. **closing.html** - Thank you/contact slide

## Usage

Each template is designed to work with any of the three provided CSS themes:
- `classic-light.css` - Clean white background (recommended default)
- `dark-mode.css` - Black background for drama
- `warm-minimal.css` - Off-white background for approachability

Simply embed the desired CSS in the `<style>` tag of each HTML file.

## Key Patterns

### Using CSS Variables
```html
<style>
  /* Embed your chosen CSS template here */
  /* Then override specific variables if needed */
  :root {
    --color-accent: #FF6B35; /* Custom accent color */
  }
</style>
```

### Layout Classes
- `.row` and `.col` - Flexible layouts (use instead of flexbox)
- `.hero-slide` - Full-height centered content
- `.split-slide` - Two-column layout
- `.placeholder` - Gray box for charts/images

### Typography Classes
- `.stat` - Large numbers (96px)
- `.accent` - Accent color text
- `.secondary` - Secondary color text
- `.caption` - Small text (18px)
- `.light`, `.medium`, `.bold` - Font weights

### Spacing Classes
- `.mb-sm`, `.mb-md`, `.mb-lg`, `.mb-xl` - Margin bottom
- `.mt-sm`, `.mt-md`, `.mt-lg`, `.mt-xl` - Margin top

## Best Practices

1. **One idea per slide** - Don't overcrowd
2. **Consistent CSS** - Embed the same stylesheet in every slide
3. **Use semantic HTML** - `<h1>`, `<h2>`, `<p>`, `<ul>` for text
4. **Leverage variables** - Colors, spacing, fonts all use CSS variables
5. **Test thumbnails** - Always generate and review thumbnail grids

## Example Workflow

```javascript
// In your conversion script
const pptxgen = require("pptxgenjs");
const { html2pptx } = require("@ant/html2pptx");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_16x9";

await html2pptx("slide1-hero-title.html", pptx);
await html2pptx("slide2-content-bullets.html", pptx);
await html2pptx("slide3-stat-focus.html", pptx);

await pptx.writeFile("output.pptx");
```
