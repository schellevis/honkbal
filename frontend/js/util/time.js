const NY_TZ = "America/New_York";
const AMS_TZ = "Europe/Amsterdam";

function nyCalendarDate(dateObj) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: NY_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(dateObj);
  const get = (type) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}${get("month")}${get("day")}`;
}

export function nyDateWindow(now, days = 5) {
  const result = [];
  const nyStr = nyCalendarDate(now);
  // Build a Date for midnight NY today
  const [y, m, d] = [nyStr.slice(0, 4), nyStr.slice(4, 6), nyStr.slice(6, 8)].map(Number);
  for (let i = 0; i < days; i++) {
    // Create date in NY: subtract i days from the NY calendar date
    const dt = new Date(Date.UTC(y, m - 1, d - i));
    result.push(dt);
  }
  return result;
}

export function mmddyyyy(date) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${m}/${d}/${y}`;
}

export function yyyymmdd(date) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}${m}${d}`;
}

export function amsHHmm(isoUtc) {
  const date = new Date(isoUtc);
  const parts = new Intl.DateTimeFormat("nl-NL", {
    timeZone: AMS_TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const get = (type) => parts.find((p) => p.type === type)?.value ?? "00";
  return `${get("hour")}:${get("minute")}`;
}
