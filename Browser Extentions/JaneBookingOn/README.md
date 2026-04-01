# JaneBookingOn

JaneBookingOn is a Chrome extension for Jane staff admin pages that automates online booking setup one staff member at a time.

## Start page

Run the extension while on a staff page such as:

- `https://vcmt.janeapp.com/admin#staff/1567`
- `https://vcmt.janeapp.com/admin#staff/1567/edit`

## Automated workflow

When you click the extension action:

1. Reads the current staff ID from the URL hash (`#staff/<id>` or `#staff/<id>/edit`).
2. If needed, routes to `#staff/<id>/edit`.
3. Waits for route/UI readiness.
4. Opens the **Online Booking** tab.
5. Ensures **Enable Online Booking** (`name="allow_online_booking"`) is enabled.
6. Ensures **Rolling Availability** (`name="max_bookable_offset"`) is set to `""` (**No Limit**).
7. Clicks **Save** and waits for save completion signals.
8. Advances to the next staff member at `#staff/<id + 1>/edit`.

## Assumptions and limitations

- Built for `https://vcmt.janeapp.com/admin*`.
- Relies on stable Jane controls by `name` attributes and visible text labels.
- If required UI controls are not present, the extension logs an error and shows an alert.
- Save completion is inferred using route/button state signals; if Jane changes save behavior, selector updates may be needed.
