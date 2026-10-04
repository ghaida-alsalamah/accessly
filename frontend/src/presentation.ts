export type Draft = { to: string; subject: string; body: string };
export type NeedResult = { name: string; status: 'CONFIRMED' | 'NOT CONFIRMED' | 'NOT APPLICABLE' | 'UNKNOWN'; evidence: string; source_quote?: string | null };
export type EventDetails = { name: string | null; date: string | null; time: string | null; location: string | null; organizer: string | null; format: string | null; url: string | null };
export type RequestRecord = { request_id: string; event_name: string; event_url: string; status: string; accommodations: Record<string, string> };
export type AgentPresentation = {
  schema_version: 1;
  presentation_status: 'ready' | 'unavailable';
  message: string;
  event: EventDetails | null;
  event_sources?: Partial<Record<keyof EventDetails, string>>;
  accessibility_results: NeedResult[];
  recommended_action: { official_contact: string | null; official_form: string | null; notice_period: string | null; recommendation: string | null } | null;
  draft: Draft | null;
  requests: RequestRecord[];
};

/** Display text only. Facts and status mapping come from the validated API schema. */
export function displayText(value: string): string {
  return value
    .replace(/[\p{Extended_Pictographic}\uFE0F\u200D]/gu, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\*\*|__|`/g, '')
    .replace(/^\s*(?:#{1,6}|>)\s*/gm, '')
    .replace(/^\s*[-*]\s+/gm, '')
    .trim();
}
