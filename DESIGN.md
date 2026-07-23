#  Naavya — Design Documentation

<div align="center">

### AI-Powered Maternal & Newborn Care Assistant

*A modern, accessible, voice-first healthcare interface built for caregivers, ASHA workers, and rural communities.*

</div>

---

# Table of Contents

- Overview
- Design Goals
- User Personas
- Design Philosophy
- Information Architecture
- User Journey
- Design System
- Color Palette
- Typography
- Layout & Spacing
- Components
- Screen Specifications
- Responsive Design
- Motion Guidelines
- Accessibility
- Error Handling
- Empty States
- Future Design Enhancements

---

# Overview

Naavya is a conversational AI healthcare assistant that helps caregivers identify the urgency of newborn symptoms using government-approved IMNCI/HBNC guidelines.

The experience has been intentionally designed to reduce anxiety rather than increase it.

Instead of providing medical diagnoses, Naavya guides users toward the appropriate next action:

- Continue Home Care
- Contact an ASHA Worker
- Visit a Healthcare Facility Immediately

The entire interface focuses on clarity, empathy, and trust.

---

# Design Goals

The product follows six major UX principles.

### 1. Voice First

Voice should always feel like the primary interaction.

Typing exists only as an alternative.

---

### 2. Simplicity

Every screen should focus on a single task.

Avoid clutter.

---

### 3. Trust

Healthcare interfaces should appear calm, spacious and reliable.

Avoid overwhelming users with technical terminology.

---

### 4. Accessibility

Every interaction should be usable regardless of age, literacy level or device quality.

---

### 5. Mobile First

Most users will access Naavya from Android smartphones.

The experience is designed mobile-first before scaling to larger screens.

---

### 6. Human-Centered

Naavya supports healthcare workers.

It never replaces them.

---

# Target Users

##  Parent / Caregiver

- First-time parents
- Rural communities
- Low digital literacy
- High emotional stress

Needs:

- Immediate assistance
- Minimal typing
- Clear instructions
- Simple language

---

##  ASHA Worker

Needs:

- Review assessments
- Track household cases
- Quickly identify urgent referrals

---

##  NGO / Evaluator

Needs:

- Understand the platform
- Review safety practices
- Evaluate usability

---

# Design Philosophy

The interface should feel similar to:

- Google Health
- Apple Health
- Headspace
- WhatsApp

Avoid looking like:

- Hospital management software
- Banking applications
- Enterprise dashboards
- Technical admin panels

---

# Information Architecture

```
Landing

├── About
├── Login
├── Register

└── Dashboard
      │
      ├── Start Assessment
      │
      ├── Voice Input
      ├── Text Input
      ├── Conversation
      ├── Processing
      └── Recommendation
      │
      ├── Assessment History
      │      └── Assessment Detail
      │
      └── Profile
```

---

# User Journey

```
Landing

↓

Start Assessment

↓

Choose Voice or Text

↓

Describe Symptoms

↓

AI Conversation

↓

Processing

↓

Recommendation

↓

Share Result
Contact ASHA
Start New Assessment
```

---

# Design System

## Primary Colors

| Color | Hex |
|--------|------|
| Primary Blue | #1565C0 |
| Secondary Blue | #42A5F5 |
| Accent Blue | #1976D2 |

---

## Neutral Colors

| Color | Hex |
|--------|------|
| Background | #F8FAFC |
| Surface | #FFFFFF |
| Text | #111827 |
| Secondary Text | #6B7280 |
| Border | #E5E7EB |

---

## Risk Indicators

| Level | Color |
|---------|---------|
| Low Risk | #2E7D32 |
| Medium Risk | #F9A825 |
| High Risk | #D32F2F |

Risk colors are reserved exclusively for recommendations and alerts.

---

# Typography

## Headings

**Font:** Poppins

- Bold
- SemiBold

---

## Body

**Font:** Inter

Readable typography with generous spacing.

Recommended sizes:

| Style | Size |
|---------|-------|
| H1 | 36px |
| H2 | 24px |
| H3 | 20px |
| Body | 16px |
| Caption | 14px |

---

# Layout

## Grid

- Mobile — 4 Columns
- Tablet — 8 Columns
- Desktop — 12 Columns

---

## Border Radius

Cards

```
24px
```

Buttons

```
24px
```

Inputs

```
16px
```

---

## Shadow

```
0 4px 16px rgba(17,24,39,0.06)
```

---

# Components

## Navigation

- Responsive Navbar
- Hamburger Menu
- Sticky Navigation

---

## Buttons

Variants:

- Primary
- Secondary
- Outline
- Text
- Danger

---

## Cards

- Feature Card
- Dashboard Card
- Recommendation Card
- Timeline Card

---

## Voice Recorder

States

- Idle
- Recording
- Review
- Uploading
- Permission Denied

---

## Chat Components

- Bot Bubble
- User Bubble
- Typing Indicator
- Quick Reply Chips

---

## Recommendation Card

Contains

- Risk Badge
- Summary
- Symptoms
- Explanation
- Recommended Action
- CTA Buttons

---

## Toasts

- Success
- Warning
- Error

---

## Modals

- Logout
- Confirmation
- Information

---

# Screen Specifications

## Landing Page

- Hero Illustration
- Primary CTA
- WhatsApp CTA
- How It Works
- Features
- Trust Section
- Footer

---

## Authentication

### Login

- Email
- Password
- Google Sign In

### Register

- Name
- Email
- Phone
- Password
- Language
- User Type

---

## Dashboard

Caregiver

- Start Voice Assessment
- Type Symptoms
- Continue WhatsApp
- Assessment History

Guest

- Same interface
- Login prompt for saved history

ASHA

- Recent Cases
- Urgent Alerts
- Assessment Tools

---

## Voice Assessment

Features

- Animated microphone
- Live waveform
- Recording timer
- Playback
- Re-record

---

## Conversation

Supports

- Multi-turn AI chat
- Voice replies
- Text replies
- Quick replies
- Session recovery

---

## Processing

Animated loading screen displaying:

- Checking symptoms...
- Reviewing guidelines...
- Preparing recommendation...

---

## Recommendation

Three outcomes

🟢 Continue Home Care

🟡 Contact ASHA Worker

🔴 Visit Hospital Immediately

Each recommendation includes

- Symptoms
- Explanation
- Next Steps
- WhatsApp Sharing
- Start New Assessment

---

## History

- Timeline View
- Filters
- Search
- Assessment Details

---

## Profile

- User Information
- Preferred Language
- Notification Settings
- WhatsApp Integration

---

## About

Contains

- Mission
- Clinical Safety
- Technology
- Privacy
- FAQ

---

# Motion Design

Animations are subtle and purposeful.

Included interactions

- Microphone Pulse
- Audio Waveform
- Chat Message Fade
- Card Elevation
- Recommendation Reveal
- Toast Animation

Reduced-motion preferences are fully respected.

---

# Responsive Design

## Mobile

Priority layout.

Single-column interface.

---

## Tablet

Split layouts where appropriate.

---

## Desktop

Centered content with maximum width.

Chat interfaces remain comfortably readable.

---

# Accessibility

Naavya follows WCAG AA guidelines.

Features include

- Keyboard navigation
- Screen-reader compatibility
- Minimum 44×44 touch targets
- Visible focus indicators
- High color contrast
- Text alternatives for icons
- Voice and text input parity

---

# Empty States

Designed empty experiences include

- No Assessments
- Empty History
- Empty Profile
- No Search Results

Each state provides

- Illustration
- Helpful explanation
- Clear call-to-action

---

# Error States

Handled scenarios

- No Internet
- Microphone Permission Blocked
- Speech Recognition Failure
- Server Timeout
- Conversation Expired
- WhatsApp Unavailable

Errors explain what happened and guide users toward recovery without exposing technical details.

---

# Future Design Enhancements

- Dark Mode
- Offline Assessment Queue
- Multi-language Interface
- Attachment Support
- Image-based Symptom Detection
- Real-time ASHA Notifications
- Progressive Web App
- Native Android Application
- Personalized Caregiver Dashboard
- Family Assessment Management

---

# Design Principles Summary

✔ Calm, trustworthy interface

✔ Mobile-first architecture

✔ Voice-first interaction

✔ Accessibility by default

✔ Government-guideline aligned

✔ Human-centered healthcare experience

✔ Built for rural accessibility

---

<div align="center">

### ❤️ Designed for caregivers. Built for impact.

**Naavya** aims to make newborn healthcare guidance more accessible through intuitive, inclusive, and trustworthy digital experiences.

</div>