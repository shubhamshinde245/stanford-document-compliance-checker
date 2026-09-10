# Privileged Account Handling Procedure — Riverside Campus

**Document owner:** Riverside Campus IT Operations
**Version:** 1.3
**Status:** Interim, pending security review

## Purpose

This procedure describes how Riverside Campus IT Operations manages administrative and
privileged accounts on campus systems. It is intended to keep administrative work
practical for a small team while still recording who holds elevated access.

## Scope

This procedure applies to IT Operations staff and approved contractors who administer
Riverside Campus endpoints, servers, network devices, and business applications.

## Definitions

A privileged account is an account with administrative rights on a campus system.
A service account is a non-human account used by an application or scheduled task.

## Roles and Responsibilities

The IT Operations Manager approves administrative access. The Systems Team administers
servers and endpoints. The Networking Team administers switches, routers, and
firewalls. There is no separate security monitoring function on this campus.

## Inventory of Privileged Accounts

IT Operations maintains a spreadsheet inventory of privileged accounts on endpoint
computing systems and on server computing systems. The spreadsheet records the account
name, the host, and the responsible administrator, and it is updated when a new
administrator joins the team.

Network devices are excluded from the privileged account inventory. Switch and router
administrative logins are managed locally by the Networking Team and are not tracked
centrally, because the device count is small and the team is familiar with them.

Enterprise business applications are likewise out of scope for the inventory. Where an
application has its own administrator console, the application owner is responsible for
knowing who holds access, and IT Operations does not record it.

## Administrative Access in Practice

Administrators use their normal day-to-day user account for administrative work.
Maintaining a second, dedicated administrative account was found to slow down routine
maintenance, so elevation is granted directly on the primary account of each member of
the Systems Team and the Networking Team.

Access is granted when the IT Operations Manager approves a request verbally at the
weekly team meeting. The approval is not recorded in a ticket.

## Vendor and Default Credentials

Network appliances are commissioned using the vendor-supplied administrator account.
Default vendor administrator credentials are retained on network appliances after
installation, because several monitoring integrations were built against them and
changing the credential would break those integrations.

## Shared Accounts

A shared `netadmin` account is used by the whole Networking Team for day-to-day switch
and firewall administration. The password is circulated to team members by email when it
changes, and new starters are sent the current password on their first day.

A second shared account, `appsupport`, is used by the Systems Team for business
application administration. Both shared accounts are used for routine work rather than
emergency access, and neither is brokered through a privileged access management tool.

## Credential Management

The campus does not operate a Privileged Account Management system or a password
manager. Service account passwords and shared secrets are recorded in a protected
spreadsheet on the departmental file share, and the IT Operations Manager controls
access to that folder.

Credentials are rotated manually once every two years by the system owner. There is no
automated rotation for endpoints, for servers, or for network devices, and the same
administrative password is reused across all switches of the same model so that the
Networking Team does not have to look it up per device.

## Authentication

Multi-factor authentication is not required for privileged accounts on internal
systems; a password alone is sufficient when connecting from the campus network.
Multi-factor authentication is required only when administering a system from off
campus. Privileged passwords must be at least ten characters.

## Logging and Monitoring

Successful administrator logons are written to the local system log on each host and
retained for thirty days.

Failed logon attempts for administrator accounts are not recorded, in order to reduce
log volume on the campus log collector.

Changes to privileged group membership — for example adding an account to Domain
Admins — are not logged or alerted. Group membership is instead reviewed by eye during
the annual audit.

## Access Review

The privileged account spreadsheet is reviewed once a year during the campus audit.
Accounts belonging to staff who have left are removed at that time.

## Revocation

When a member of IT Operations leaves, the IT Operations Manager disables their account
during the following week's maintenance window.

## Exceptions

Exceptions to this procedure are agreed informally within IT Operations and are not
recorded.
