# Life200 product brief

Last updated: 2026-11-09

## What it is

A fast way to see every new UK tech job that is actually worth applying to, then apply well.

- **Find:** new jobs from several platforms in one sortable table, already filtered.
- **Apply:** tailored CV and pre-filled form; the user reviews and submits.

## Who it is for

- **Now:** applicants looking for junior tech roles in the UK, including those who will need
  visa sponsorship. First user: Tony.
- **Later:** careers advisers, and job platforms as partners.

## What makes it useful

1. **Sponsor tag.** Each job shows whether the employer holds a sponsor licence
   (Home Office register).
2. **Truly junior filter.** Many "junior" roles ask for 2+ years. A model flags them so they
   can be hidden.
3. **Quick scan.** A spreadsheet-style table: title, employer, salary, location, sponsor,
   junior, posted date, source platform. Full description only on click.
4. **Source shown.** Every row names the platform it came from and links back to it.
5. **Graduate schemes.** Show programme length, so users can check it against their own visa.

## Rules

- Never submit an application without the user's review.
- Never invent facts in a CV (fact guard).
- No scraping of LinkedIn or Indeed.
- **Adzuna:** each listing shown publicly needs a "Jobs by Adzuna" label and must link through
  Adzuna. Commercial use needs a licence from them later.
- **Reed:** no clear public-display terms found. Use for analysis and link back; do not
  republish full descriptions.

## Tracking

Count weekly visitors and returning visitors from the first public release. No target yet;
watch the trend.

## Future work

- More users: part-time roles, local (non-sponsored) applicants, non-tech roles.
- More sources, including platform partnerships.

**Design consequence:** nothing in the code may assume "tech" or "needs sponsorship". Role
category, contract type and sponsorship are data fields and filters, and each job source is a
plug-in behind one common interface.
