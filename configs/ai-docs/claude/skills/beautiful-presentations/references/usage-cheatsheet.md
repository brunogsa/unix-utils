# Beautiful Presentations — Usage Cheatsheet

Common slide patterns, do/don't lists, and tips. Companion to `design-principles.md` (the full reference). Load this when authoring slides.

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
- Cram multiple ideas onto one slide
- Use more than one font family
- Mix too many colors (stick to 3-4)
- Create inconsistent spacing
- Use low-quality or generic stock photos
- Add unnecessary animations or transitions
- Center-align everything (causes visual chaos)
- Forget margins (minimum 60px)

**Do:**
- One clear idea per slide
- Consistent font weights and sizes
- Monochromatic or two-tone palette
- Systematic spacing using CSS variables
- Professional, authentic imagery
- Minimal or no transitions
- Strategic alignment (left for text, center for titles)
- Generous white space throughout

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
