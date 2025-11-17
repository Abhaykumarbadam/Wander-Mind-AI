# WanderMind AI - Chat UI Layout Reference

## Desktop Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              NAVBAR (Fixed)                              │
│  [Logo] [Dashboard] [Chat] [Itinerary] [Maps] [Transport] [Features]   │
│                                                            [Logout]      │
└─────────────────────────────────────────────────────────────────────────┘
│                                                                           │
│  MAIN CONTENT CONTAINER (max-width: 1200px)                              │
│                                                                           │
│  On #chat section:                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                        CHAT HEADER                                  │ │
│  │  [AI Travel Concierge] [Profile Chip] [New Chat Button]            │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────┬───────────────────────────────────────────┐ │
│  │   SIDEBAR              │         MAIN CHAT AREA                    │ │
│  │ ┌──────────────────┐  │ ┌───────────────────────────────────────┐│ │
│  │ │  Chat History   │  │ │     MESSAGES CONTAINER                 ││ │
│  │ │  [≡ toggle]    │  │ │                                         ││ │
│  │ ├──────────────────┤  │ │  User: "Tell me about Paris" ─────►   ││ │
│  │ │                  │  │ │                                    [✓]││ │
│  │ │ [Session 1]     │  │ │  Aura: "Paris is a beautiful city..." ││ │
│  │ │ Nov 16, 5:30pm  │  │ │  Lorem ipsum dolor sit amet...        ││ │
│  │ │                  │  │ │                                         ││ │
│  │ │ [Session 2]     │  │ │                                         ││ │
│  │ │ Nov 15, 2:45pm  │  │ │  User: "What about the Eiffel Tower?" ││ │
│  │ │                  │  │ │                                    [✓]││ │
│  │ │ [Session 3]     │  │ │                                         ││ │
│  │ │ Nov 14, 9:20am  │  │ │  ⏳ Aura typing...                    ││ │
│  │ │                  │  │ │  ⊙ ⊙ ⊙                               ││ │
│  │ │ No previous...  │  │ │                                         ││ │
│  │ │                  │  │ └───────────────────────────────────────┘│ │
│  │ └──────────────────┘  │                                             │ │
│  │                        │ ┌───────────────────────────────────────┐│ │
│  │                        │ │   CHAT INPUT SECTION                  ││ │
│  │                        │ │ ┌───────────────────────────────────┐ ││ │
│  │                        │ │ │ Ask your AI travel assistant...   │ ││ │
│  │                        │ │ │ (supports markdown, Enter to send)│[➤]││
│  │                        │ │ │                                   │   ││ │
│  │                        │ │ └───────────────────────────────────┘ ││ │
│  │                        │ │ Press Enter to send, Shift+Enter for  ││ │
│  │                        │ │ new line                              ││ │
│  │                        │ └───────────────────────────────────────┘│ │
│  │                        │                                             │ │
│  └────────────────────────┴───────────────────────────────────────────┘ │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

Other Sections:
├─ Dashboard: Welcome message + stats (trips, days, upcoming)
├─ Itinerary: Expandable day-by-day plan with times and activities
├─ Maps: Placeholder for map integration
├─ Transport: Placeholder for transport options
└─ Features: Feature cards grid (Adaptive Itineraries, Conversational, etc.)
```

## Mobile Layout Structure (≤600px)

```
┌────────────────────────────┐
│  [Menu] WanderMind [Logout]│
└────────────────────────────┘

┌────────────────────────────┐
│  CHAT HEADER               │
│  [AI Travel Concierge]     │
│  [Profile Chip]            │
│  [New Chat Button]         │
└────────────────────────────┘

SIDEBAR (Full width, collapsible):
┌────────────────────────────┐
│ Chat History      [toggle] │
├────────────────────────────┤
│ [Session 1]               │
│ Nov 16, 5:30pm            │
│                           │
│ [Session 2]               │
│ Nov 15, 2:45pm            │
└────────────────────────────┘

MESSAGES (Full width):
┌────────────────────────────┐
│ User: "Tell me about..."   │
│                           │
│ Aura: "Paris is..." etc.  │
│ ...                       │
└────────────────────────────┘

INPUT (Full width):
┌────────────────────────────┐
│ Ask your AI assistant...   │
│ (multiline textarea)       │
│                      [➤]   │
│ Press Enter to send...     │
└────────────────────────────┘
```

## Color Scheme

**Background & Cards:**
- Primary BG: #ffffff (white)
- Secondary BG: #f8f9fa (light gray)
- Glass overlay: rgba(255,255,255,0.95) with backdrop-filter blur

**Accent Colors:**
- Primary Blue: #5b8cff
- User Message Gradient: #7f5af0 → #5b21b6 (purple)
- Assistant Message: White with subtle blue border

**Text:**
- Primary: #111827 (dark charcoal)
- Secondary: #475569 (muted gray)
- Muted: #64748b (lighter gray)

**Shadows:**
- Card: 0 20px 60px rgba(8,18,38,0.06)
- Hover: 0 28px 80px rgba(8,18,38,0.1)
- Input: inset 0 -6px 18px rgba(0,0,0,0.02)

## Component Styling Details

### Profile Chip
```
┌──────────────────────────────────────────┐
│ [Avatar] Name [✏ Edit Details]           │
└──────────────────────────────────────────┘
- Pill-shaped (border-radius: 999px)
- Glassmorphic background
- Gradient circular avatar (28px)
- Emoji or initials in avatar
```

### New Chat Button
```
┌─────────────────┐
│ + New Chat      │
└─────────────────┘
- Gradient background: #667eea → #764ba2
- Hover: Lift effect (translateY -2px)
- Icon + text layout
```

### Chat Messages

**User Message:**
```
                              ┌──────────────────────┐
                              │ Tell me about Paris! │
                              └──────────────────────┘
- Right-aligned
- Purple gradient (#7f5af0 → #5b21b6)
- White text
- Rounded corners with custom tail
- Max width: 85% of container
```

**Assistant Message:**
```
┌──────────────────────────────────────────────┐
│ Paris is a beautiful city known for its art, │
│ culture, and architecture. The Eiffel Tower   │
│ is one of the most iconic landmarks...        │
└──────────────────────────────────────────────┘
- Left-aligned
- White background with blue border
- Supports markdown formatting
- Max width: 85% of container
```

**Typing Indicator:**
```
┌──────────────────┐
│ ⊙ ⊙ ⊙            │
└──────────────────┘
- Three animated pulsing dots
- Slight lift animation
- Appears while waiting for response
```

### Chat Input
```
┌──────────────────────────────────────────┬────┐
│ Ask your AI travel assistant...          │ ➤  │
│ (Auto-resizable textarea: 44-120px)      │    │
└──────────────────────────────────────────┴────┘
Press Enter to send, Shift+Enter for new line

- Textarea with auto-resize
- Blue focus border
- Disabled send button while loading
- Spinner during API call
```

### Sidebar Sessions
```
┌────────────────────────────┐
│ Chat History         [≡]   │
├────────────────────────────┤
│ ▶ Paris Trip Planning      │
│   Nov 16, 5:30pm          │
│                           │
│ ▶ Tokyo Adventure         │
│   Nov 15, 2:45pm          │
│                           │
│ No previous chats         │
└────────────────────────────┘

- Each session is clickable
- Shows title + timestamp
- Active session highlighted
- Hover effect (light background, slight translate)
- Collapse toggle button
```

## Animations & Transitions

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Message appear | Fade in + slide up | 0.32s | cubic-bezier(.2,.9,.2,1) |
| Typing dots | Pulse | 1.6s | infinite |
| Send button hover | Lift + scale | 0.18s | cubic-bezier(.2,.9,.2,1) |
| Sidebar collapse | Slide + fade | 0.3s | ease |
| Profile chip hover | Subtle lift | 0.2s | ease |
| New chat button hover | Lift + glow | 0.2s | ease |
| Message scroll | Smooth scroll | 0.2s | smooth behavior |
| Input focus | Border + glow | 0.2s | ease |

## Responsive Breakpoints

```
Desktop (1000px+):
- Full sidebar visible (280px)
- Chat main area takes remaining space
- Standard spacing and typography

Tablet (600-1000px):
- Sidebar still visible but narrower
- Chat area adjusted
- Slightly smaller typography

Mobile (<600px):
- Sidebar collapses (full-width toggle)
- Messages stack full-width
- Larger touch targets
- Reduced horizontal padding
```

## Accessibility Features

✅ **ARIA Labels:**
- Chat messages have role="log" with aria-live="polite"
- Buttons have descriptive aria-labels
- Navigation has role="navigation"
- Regions have role="region" and aria-label

✅ **Keyboard Navigation:**
- Tab through all interactive elements
- Enter/Space to activate buttons
- Shift+Tab for reverse navigation
- Escape to close sidebars (future enhancement)

✅ **Focus Indicators:**
- Blue focus ring on all interactive elements
- Visible on keyboard navigation
- Meets WCAG 2.1 AA standards

✅ **Color Contrast:**
- Text colors meet WCAG AA standards
- Links have sufficient contrast
- Icons have fallback text descriptions

✅ **Screen Reader Support:**
- Semantic HTML structure
- Descriptive button labels
- Live region updates announced
- Skip navigation links (in navbar)
