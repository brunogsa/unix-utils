---
name: beautiful-presentations
description: USE for Apple-inspired minimalist business presentations. Trigger when the user asks for a polished business deck, pitch deck, executive presentation, product launch, or modern professional aesthetic.
---

# Beautiful Presentations - Apple-Inspired Minimalist Design

Create stunning, minimalist business presentations inspired by Apple's design philosophy.

This skill provides comprehensive design principles, pre-built CSS templates, and best practices for crafting pitch decks that are clean, elegant, and highly effective.

## When to Use This Skill

Use this skill when:

- Creating business pitch decks with modern, minimalist design
- Building investor presentations that need professional polish
- Designing product launch presentations
- Developing executive-level reports and updates
- Crafting sales presentations that emphasize clarity over clutter
- Any presentation where Apple-inspired aesthetics are desired
- The user explicitly requests "beautiful," "clean," "minimalist," or "modern" presentations
- The user mentions Apple, minimalism, or similar design philosophies

## Core Philosophy

This skill embodies three fundamental principles:

1. **Less is More** - Every element must earn its place on the slide
2. **Clarity Over Cleverness** - Prioritize clear communication over decoration
3. **White Space is Design** - Empty space creates focus and elegance

## How to Use This Skill

### Step 1: Read Design Principles (REQUIRED)

Before creating any presentation, ALWAYS read the comprehensive design principles reference:

```bash
# Read the complete design principles document
cat references/design-principles.md
```

This document contains:
- Typography guidelines and font selection
- Color palette principles and Apple-inspired schemes
- Layout composition rules and patterns
- White space best practices
- Visual elements guidance (images, icons, charts)
- Presentation flow and pacing
- Quality checklist

### Step 2: Choose a Design Theme

Select one of three pre-built CSS templates based on the presentation's tone:

**Classic Light** (`assets/classic-light.css`)
- Clean white background (#FFFFFF)
- Professional and versatile
- Best for: Most business presentations, investor pitches
- Accent color: Apple blue (#0071E3)

**Dark Mode** (`assets/dark-mode.css`)
- Black background (#000000)
- Dramatic and modern
- Best for: Product launches, tech presentations, evening events
- Accent color: Bright blue (#0A84FF)

**Warm Minimal** (`assets/warm-minimal.css`)
- Off-white background (#FAFAF8)
- Friendly and approachable
- Best for: Internal presentations, team updates, creative pitches
- Accent color: Warm orange (#FF6B35)

### Step 3: Plan the Presentation Structure

Before writing any code, create a detailed outline:

1. **Define the core message** - What's the one key takeaway?
2. **Outline slide types needed**:
   - Title slide (hero)
   - Problem statement
   - Solution overview
   - Key benefits (3-5 slides)
   - Supporting evidence/data
   - Call to action
   - Closing

3. **For each slide, specify**:
   - Main message (5-8 words for headlines)
   - Layout pattern (hero, split, stat-focus, content-bullets)
   - Visual elements needed (charts, images, icons)
   - Presenter notes (1-3 sentences)

### Step 4: Reference Example Slide Templates

The skill provides example HTML templates in the `assets/` directory:

- `hero-title.html` - Opening/title slides with centered text
- `content-bullets.html` - Standard content with bullet points (max 5)
- `stat-focus.html` - Large statistics with context
- `split-content.html` - Two-column layout with text and visual

View these examples to understand proper HTML structure and CSS class usage.

### Step 5: Create HTML Slides Using html2pptx Workflow

Follow the standard pptx skill html2pptx workflow with design enhancements:

1. **Read html2pptx documentation** (from pptx skill):
   ```bash
   # This is external to the beautiful-presentations skill
   # It's part of the standard pptx skill
   cat /mnt/skills/public/pptx/html2pptx.md
   ```

2. **Create shared CSS file** that embeds your chosen theme:
   ```css
   /* shared-styles.css */
   /* Copy contents from assets/classic-light.css (or dark-mode.css or warm-minimal.css) */
   
   /* Optional: Override specific variables for customization */
   :root {
     --color-accent: #FF6B35; /* Custom accent if needed */
   }
   ```

3. **Create HTML file for each slide** following these rules:
   - Body dimensions: `960px × 540px` (16:9 aspect ratio)
   - Embed the shared CSS in a `<style>` element
   - Use semantic HTML: `<h1>`, `<h2>`, `<p>`, `<ul>`, `<ol>`
   - Use CSS variables for colors, spacing, typography
   - Use `row`, `col`, `fit` classes for layout (NOT flexbox directly)
   - Use `class="placeholder"` for chart/image areas
   - Use `data-balance` attribute on headlines for better typography

4. **Apply design principles from reference**:
   - One idea per slide
   - Maximum 5 bullet points
   - Generous margins (60px minimum)
   - Consistent spacing between elements
   - Strategic use of accent color
   - Sufficient contrast for readability

5. **Create conversion script** using html2pptx:
   ```javascript
   const pptxgen = require("pptxgenjs");
   const { html2pptx } = require("@ant/html2pptx");

   const pptx = new pptxgen();
   pptx.layout = "LAYOUT_16x9";

   await html2pptx("slide1-hero.html", pptx);
   await html2pptx("slide2-content.html", pptx);
   // ... add all slides

   await pptx.writeFile("output.pptx");
   ```

6. **Run conversion**:
   ```bash
   NODE_PATH="$(npm root -g)" node convert.js 2>&1
   ```

### Step 6: Visual Validation (CRITICAL)

Always validate the presentation visually before delivering:

1. **Generate thumbnail grid**:
   ```bash
   python /mnt/skills/public/pptx/scripts/thumbnail.py output.pptx workspace/thumbnails --cols 4
   ```

2. **Inspect thumbnails for**:
   - Text cutoff or overflow
   - Text overlapping with shapes/images
   - Content too close to edges
   - Insufficient color contrast
   - Inconsistent spacing
   - Misaligned elements

3. **Fix issues** by adjusting HTML margins, spacing, or colors and regenerate

4. **Repeat** until all slides are visually perfect

### Step 7: Final Quality Check

Before delivering the presentation, verify the quality checklist from design-principles.md:

**Visual Consistency:**
- [ ] Single font family used throughout
- [ ] Consistent color palette (3-4 colors maximum)
- [ ] Uniform spacing between elements
- [ ] All elements aligned to grid
- [ ] Consistent image treatment

**Content Quality:**
- [ ] One main idea per slide
- [ ] No more than 5 bullet points per slide
- [ ] Text scannable in 5 seconds
- [ ] All data cited/sourced
- [ ] No spelling or grammar errors

**Technical Quality:**
- [ ] All images high resolution
- [ ] No text overflow
- [ ] Sufficient color contrast
- [ ] Fast loading
- [ ] Tested on target screen

## Design Guidelines Summary

### Typography Rules
- **Font**: Use system fonts (SF Pro Display, Helvetica Neue, Inter)
- **Hierarchy**: Title 48-72px, Body 26px, Caption 18px, Stats 96-120px
- **Weights**: Vary weight (Light, Regular, Medium, Bold) not font family
- **Line height**: 1.1 for headlines, 1.4-1.6 for body text

### Color Rules
- **Monochromatic preferred**: Black/white + single accent color
- **60-30-10 rule**: 60% background, 30% text, 10% accent
- **Limit accent usage**: Only for emphasis and key data
- **High contrast**: Ensure text readability (WCAG AA minimum)

### Layout Rules
- **Margins**: Minimum 60px on all sides
- **Grid system**: Align to 12-column grid
- **One idea per slide**: Don't combine multiple concepts
- **White space**: Let content breathe, don't fill every pixel

### Content Rules
- **Headlines**: 5-8 words, action-oriented
- **Bullets**: 3-5 maximum, one line each preferred
- **Slides**: 50-100 words optimal, 150 maximum
- **Data**: Round numbers, include context, highlight insights

## Common Patterns

### Hero/Title Slide
```html
<div class="hero-slide">
  <h1 data-balance>Your Big Idea in <span class="accent">8 Words</span></h1>
  <p class="subtitle light">Supporting context or tagline</p>
</div>
```

### Content with Bullets
```html
<h2>Key Benefits</h2>
<ul>
  <li>First benefit in one concise line</li>
  <li>Second benefit with clear value</li>
  <li>Third benefit with impact</li>
</ul>
```

### Large Statistic
```html
<div class="hero-slide">
  <div class="stat">87%</div>
  <p class="caption secondary">Supporting context for the number</p>
</div>
```

### Split Layout
```html
<div class="row">
  <div class="col">
    <h2>Section Title</h2>
    <p>Your content here</p>
  </div>
  <div class="col">
    <div class="placeholder">Chart or Image</div>
  </div>
</div>
```

## Avoiding Common Mistakes

**Don't:**
- ❌ Cram multiple ideas onto one slide
- ❌ Use more than one font family
- ❌ Mix too many colors (stick to 3-4)
- ❌ Create inconsistent spacing
- ❌ Use low-quality or generic stock photos
- ❌ Add unnecessary animations or transitions
- ❌ Center-align everything (causes visual chaos)
- ❌ Forget margins (minimum 60px)

**Do:**
- ✅ One clear idea per slide
- ✅ Consistent font weights and sizes
- ✅ Monochromatic or two-tone palette
- ✅ Systematic spacing using CSS variables
- ✅ Professional, authentic imagery
- ✅ Minimal or no transitions
- ✅ Strategic alignment (left for text, center for titles)
- ✅ Generous white space throughout

## Example Request Handling

**User request**: "Create a pitch deck about our Q4 results with a modern, minimal design"

**Response process**:
1. Read design-principles.md for guidelines
2. Choose classic-light.css (professional business context)
3. Plan structure: Title → Executive Summary → Key Metrics → Revenue → Growth → Future → CTA
4. Create HTML slides embedding classic-light.css
5. Use stat-focus slides for key numbers (87% growth)
6. Use split-content for revenue breakdown with chart
7. Generate presentation with html2pptx
8. Create thumbnail grid for validation
9. Review for text overflow, spacing, contrast
10. Deliver final .pptx with download link

## Tips for Excellence

1. **Start with the message**: Design serves the content, not vice versa
2. **Use the checklist**: Reference design-principles.md quality checklist
3. **Think in systems**: Use CSS variables consistently
4. **Trust white space**: Resist urge to fill empty areas
5. **Test thumbnails**: Always generate and inspect before delivering
6. **Stay on brand**: Maintain consistency throughout presentation
7. **Less animation**: Static slides are often more powerful
8. **Real photography**: Avoid generic stock images when possible
9. **Round numbers**: 87% is cleaner than 86.7%
10. **One bold statement**: Better than three weak points

## Troubleshooting

**Text overflow in slides?**
- Reduce font size or word count
- Increase slide margins
- Break into multiple slides

**Colors look off?**
- Verify CSS variable overrides are correct
- Check contrast ratios for accessibility
- Stick to the provided color palettes

**Spacing inconsistent?**
- Use CSS spacing variables (--space-sm, --space-md, etc.)
- Don't use arbitrary pixel values
- Apply utility classes (.mb-lg, .mt-md)

**Slides don't feel minimalist?**
- Remove decorative elements
- Reduce bullet points
- Increase white space
- Simplify color usage
- One idea per slide

## Resources Included

**References:**
- `design-principles.md` - Comprehensive design guide (MUST READ)

**Assets:**
- `classic-light.css` - White background theme
- `dark-mode.css` - Black background theme  
- `warm-minimal.css` - Off-white background theme
- `hero-title.html` - Example title slide
- `content-bullets.html` - Example content slide
- `stat-focus.html` - Example stat slide
- `split-content.html` - Example split layout
- `README.md` - Asset usage guide

---

*Remember: Minimalism is not about using less—it's about making room for more of what matters.*
