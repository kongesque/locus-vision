# LocusVision - Beta Shipping Plan

This document outlines the focused shipping plan for the upcoming LocusVision Beta release. The goal is to deliver a functional MVP while maximizing visual impact ("WOW Factor") for showcases such as Reddit, Hacker News, and early demos.

**Current Status:**
- **MVP Features**: 100% Complete (5/5)
- **WOW Factors**: 16% Complete (1/6)
- **Overall**: 54% Complete

---

## 🚀 1. Immediate Focus: Unblock Core MVP (⭐)
*These features are strictly necessary for the platform to function as a complete end-to-end beta product.*

### Frontend & Tracking
- [x] **Zone Occupancy Tracking**: Real-time frontend tracking of current count within a zone.

### Analytics & Reporting
- [x] **Peak Hours Identification**: Pinpoint and visualize the busiest times within zones.

### Live Dashboard
- [x] **Multi-camera Grid (2x2, 3x3)**: Allow users to view multiple camera streams simultaneously.
- [x] **Real-time Zone Counts Overlay**: Display live counting metrics directly over the video feeds.
- [x] **Current Occupancy Display**: High-level dashboard widget showing total current occupancy.

---

## 🔥 2. High-Impact Showcases: "WOW Factors"
*These features differentiate the product visually and demonstrate advanced spatial intelligence. Prioritize these for demo videos and marketing material.*

### Deep Movement Insights
- [ ] **Path Analysis**: Visualize the most common routes people take through a space. 
  - *Impact*: "See the invisible flows of your business."
- [ ] **Group Detection**: Identify and track people moving together as a single entity or family unit.
  - *Impact*: Advanced behavioral AI that goes beyond simple counting.
- [ ] **Anomaly Detection**: Highlight unusual movement patterns (e.g., someone moving against the flow, running, or accessing restricted areas).
  - *Impact*: Actionable, intelligent security/safety insights.

### Advanced Visualizations
- [x] **Real-time Data Streaming (WebSocket/SSE)**: Live, zero-latency dashboard updates as events happen.
  - *Impact*: Shows off the speed and efficiency of the edge pipeline.
- [ ] **Flow Diagrams (Sankey)**: Visually represent how crowds transition from Zone A to Zone B.
  - *Impact*: Highly engaging, data-rich visuals perfect for dashboard screenshots.
- [ ] **Live Heatmap Overlay**: Real-time generation of heatmaps superimposed on the live stream.
  - *Impact*: Instantly understandable value proposition; looks great in video format.

---

## 📋 Recommended Execution Order

To maximize momentum leading up to the Beta launch:

1. **Week 1: Unblock the Dashboard (MVP + Quick Wins)**
   * Implement real-time Zone Occupancy Tracking and Current Occupancy Display.
   * Add the Multi-camera Grid.
   * *Status: You now have a working, multi-camera dashboard.*

2. **Week 2: The Data Foundation & Basic Visuals**
   * Build Real-time Data Streaming (WebSockets) to make the UI feel alive.
   * Integrate Real-time Zone Counts Overlay on the video feeds.
   * Implement Peak Hours Identification.

3. **Week 3: Deep Visual Impact (The "WOW" sprint)**
   * Build the Live Heatmap Overlay.
   * Create Sankey Flow Diagrams based on zone transitions.
   * *Status: You now have highly shareable visuals for Reddit/Twitter.*

4. **Week 4: Advanced AI Behaviors (The Differentiators)**
   * Implement Group Detection and Path Analysis.
   * Add Anomaly Detection.
   * *Status: Product is ready for Beta launch with a strong technological moat.*

---

## 🪝 3. Extensibility: Webhooks & Integrations
*To make the product sticky and useful for enterprise beta testers, we need to allow data to flow out of LocusVision into external systems.*

- [ ] **Event-driven Webhooks**: Fire POST requests when specific events occur (e.g., `zone_entered`, `capacity_exceeded`, `anomaly_detected`).
- [ ] **Scheduled Summaries**: Webhooks that send daily or hourly aggregated payload summaries.
- [ ] **Webhook Management UI**: A settings page to register endpoint URLs, configure authentication headers, and select event subscriptions.
  - *Impact*: Transforms the app from a standalone dashboard into a powerful infrastructure component.
