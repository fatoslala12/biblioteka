# UI QA Checklist (Admin + Member)

Use this checklist before every deploy to eliminate visual regressions and UX breakage.

## 1) Core Layout and Responsive
- [ ] Test mobile widths: 360px, 390px, 430px.
- [ ] Test tablet width: 768px.
- [ ] Test desktop widths: 1366px and 1920px.
- [ ] No horizontal page overflow in admin and member pages.
- [ ] Header/topbar remains stable and usable on scroll.

## 2) Design System Consistency
- [ ] Spacing uses token values (`--sl-space-*`) and looks uniform.
- [ ] Radius uses token values (`--sl-radius-*`) on cards/buttons/inputs.
- [ ] Typography follows scale 12/14/16/20/28.
- [ ] Shadows are from token set (`--sl-shadow-*`), not random values.
- [ ] Card headers follow same hierarchy (title + subtitle + actions alignment).

## 3) Reusable Component Checks
- [ ] `FilterBar` style appears consistent on changelist pages.
- [ ] `ActionPills` buttons are compact and readable.
- [ ] `DataCard` and `StatTile` look visually consistent.
- [ ] `TableWrap` supports horizontal scroll on small devices.
- [ ] Buttons and links keep consistent focus ring/hover/active states.

## 4) Admin Functional Smoke
- [ ] Admin login redirects correctly to custom sign in page.
- [ ] Admin logout redirects to homepage.
- [ ] Book list loads and table is readable on mobile.
- [ ] Reservation list loads and action buttons are usable on mobile.
- [ ] Reservation request list shows "Aktiviteti i fundit" and proper action labels.
- [ ] Reservation request detail shows audit timeline entries.
- [ ] Fine list/detail surfaces latest activity and timeline blocks.
- [ ] Policy detail page shows audit timeline block.
- [ ] Book detail page has no duplicate header/title block.

## 5) Member Portal Smoke
- [ ] Sign in page opens and allows login flow.
- [ ] Member dashboard loads without broken cards.
- [ ] Active loans table is readable and horizontally scrollable on mobile.
- [ ] Charts remain readable and do not overflow.
- [ ] Profile/edit blocks stay centered and text is readable.

## 6) Accessibility and Interaction
- [ ] Keyboard tab order works for nav/search/actions.
- [ ] Focus visible ring appears on interactive controls.
- [ ] Color contrast is readable on buttons and text.
- [ ] Hover and active states include subtle motion/feedback.

## 7) Browser Pass
- [ ] Chrome (latest) mobile + desktop.
- [ ] Edge (latest) desktop.
- [ ] Firefox (latest) desktop.

## 8) Release Decision
- [ ] All checklist items pass.
- [ ] Critical UI bugs: 0.
- [ ] New regression screenshots attached when any issue is found.
- [ ] Deploy approved.

## 9) Operations
- [ ] Run `python manage.py daily_ops_report` and review metrics.
- [ ] Run `python manage.py expire_reservations` before shift opens (or scheduler/cron).
