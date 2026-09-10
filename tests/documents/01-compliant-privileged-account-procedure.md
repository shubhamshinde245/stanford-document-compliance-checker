# Privileged Account Management Operating Procedure

**Document owner:** Identity and Access Management, Office of the CISO
**Version:** 4.2
**Status:** Approved by the Information Security Steering Committee

## Purpose

This procedure describes how the University provisions, inventories, monitors, and
revokes privileged accounts across institutional systems. It exists to ensure that
administrative access is granted deliberately, recorded accurately, and withdrawn
promptly, and it supports the University information security program.

## Scope

This procedure applies to all staff, contractors, student employees, and vendors who
hold or grant administrative, root, domain administrator, database owner, hypervisor
administrator, or service account credentials on any endpoint, server, network device,
or enterprise business application owned or operated by the University, including
cloud tenancies and research computing environments.

## Definitions

A privileged account is any account whose permissions exceed those of a standard user.
A dedicated privileged account is an administrative account that is separate from the
holder's day-to-day user account. A break-glass account is an emergency account used
only when normal administrative paths are unavailable.

## Roles and Responsibilities

The Identity and Access Management team operates the tooling and maintains the
inventory. System owners approve and review access for the systems they own. The
Security Operations Centre monitors privileged activity and responds to alerts. Human
Resources notifies Identity and Access Management of joiners, movers, and leavers. The
Chief Information Security Officer approves exceptions.

## Inventory of Privileged Accounts

The Identity and Access Management team maintains an authoritative inventory of every
privileged account. The inventory explicitly covers privileged accounts configured on
endpoint computing systems, on server computing systems, on network devices, and on
enterprise business applications. No system class is excluded.

For each account the inventory records the account name, the owning system, the system
class, the responsible individual, the account type, and the business justification.
The inventory is reconciled against directory services and cloud identity providers
every quarter, and discrepancies are resolved within ten business days.

## Authorization and Dedicated Accounts

Every privileged account on an endpoint computing system, a server computing system, a
network device, or an enterprise business application must be individually authorized
by the system owner before it is created. Authorization is recorded in the access
request ticket and retained for the life of the account plus three years.

Administrators must use a dedicated named administrative account that is distinct from
their day-to-day user account. Performing administrative work from a standard user
account is prohibited on every system class.

## Default Credentials

Default vendor administrator credentials are changed before any system is placed into
service. No default privileged account authenticates using its factory-supplied
credential. Build checklists require the change to be evidenced, and quarterly scans
identify any device still presenting a known default credential.

## Shared Accounts

Shared privileged accounts are not permitted for workforce members. The only exceptions
are documented emergency break-glass accounts and accounts brokered through the
Privileged Account Management system, which issues credentials to a named individual
for a bounded session and attributes every action to that person.

Break-glass credentials are stored sealed in the Privileged Account Management vault.
Their use triggers an automatic alert to the Security Operations Centre, and the
credential is rotated and resealed after each use.

## Privileged Account Management System

The University operates an enterprise Privileged Account Management system. It is the
system of record for service accounts, shared accounts, and shared secrets held between
workforce members, and every such credential is documented within it.

The Privileged Account Management system automatically rotates credentials on a defined
schedule, issuing a unique credential to each endpoint computing system and to each
server computing system, so that no credential is reused across hosts. The same
automatic rotation with unique per-device credentials is applied to every managed
network device.

## Authentication

The University Identity Providers require multi-factor authentication for all
privileged accounts at every interactive login, with no exemption for internal or
on-campus systems. Passwords for privileged accounts must be at least sixteen
characters and must not be reused across systems. Interactive login for service
accounts is disabled.

## Logging, Alerting, and Monitoring

The University Identity Providers log and alert whenever a change is made to a
privileged group membership, including additions, removals, and nesting changes. The
alert is delivered to the Security Operations Centre within five minutes.

The Identity Providers also log and alert on account logon events for all privileged
accounts, capturing both successful and failed authentication attempts. Logs are
retained for one year. The Security Operations Centre reviews privileged session alerts
daily and investigates anomalies within one business day.

## Access Review

System owners review the privileged account list every quarter and confirm in writing
that each account is still required for a documented business purpose. Accounts not
confirmed during the review are disabled within five business days and deleted after
ninety days if no appeal is filed.

## Revocation

Privileged access is revoked on the same business day that an individual changes role
or leaves the University. Human Resources notifies the Identity and Access Management
team through the automated leaver feed, and the team confirms revocation within four
hours.

## Exceptions

Any exception to this procedure requires written approval from the Chief Information
Security Officer, is recorded in the exception register, and is reviewed annually.
